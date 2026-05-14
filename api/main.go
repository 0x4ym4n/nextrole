package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

type Embedder func(context.Context, string) ([]float64, error)

func encoder(endpoint, model, revision string) Embedder {
	client := &http.Client{Timeout: 20 * time.Second}
	return func(ctx context.Context, text string) ([]float64, error) {
		body, _ := json.Marshal(map[string]string{"text": text})
		r, err := http.NewRequestWithContext(ctx, "POST", endpoint+"/embed", bytes.NewReader(body))
		if err != nil {
			return nil, err
		}
		r.Header.Set("Content-Type", "application/json")
		res, err := client.Do(r)
		if err != nil {
			return nil, err
		}
		defer res.Body.Close()
		if res.StatusCode != 200 {
			return nil, fmt.Errorf("embedding service status %d", res.StatusCode)
		}
		var e struct {
			Vector   []float64 `json:"embedding"`
			Model    string    `json:"model"`
			Revision string    `json:"revision"`
		}
		if err = json.NewDecoder(io.LimitReader(res.Body, 100000)).Decode(&e); err != nil {
			return nil, err
		}
		if e.Model != model || e.Revision != revision {
			return nil, fmt.Errorf("embedding model/revision differs from corpus")
		}
		return e.Vector, nil
	}
}
func send(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func fail(w http.ResponseWriter, status int, message string) {
	send(w, status, map[string]string{"error": message})
}
func handler(c Corpus, embed Embedder, threshold float64) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		send(w, 200, map[string]any{"status": "ok", "jobs": len(c.Jobs), "dataset": c.Dataset, "model": c.Model, "revision": c.Revision, "dimension": c.Dimension, "threshold": threshold, "semantic_configured": embed != nil})
	})
	mux.HandleFunc("GET /api/v1/metadata", func(w http.ResponseWriter, r *http.Request) {
		countries, sources := map[string]bool{}, map[string]bool{}
		for _, j := range c.Jobs {
			if j.Country != "" {
				countries[j.Country] = true
			}
			sources[j.Source] = true
		}
		keys := func(m map[string]bool) []string {
			a := []string{}
			for k := range m {
				a = append(a, k)
			}
			sort.Strings(a)
			return a
		}
		send(w, 200, map[string]any{"countries": keys(countries), "sources": keys(sources), "jobs": len(c.Jobs), "dataset": c.Dataset, "collected_at": c.CollectedAt, "model": c.Model, "threshold": threshold})
	})
	mux.HandleFunc("POST /api/v1/search", func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		if !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
			fail(w, 415, "use application/json")
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 40*1024)
		dec := json.NewDecoder(r.Body)
		dec.DisallowUnknownFields()
		var q Request
		if err := dec.Decode(&q); err != nil {
			fail(w, 400, "invalid JSON or unsupported field")
			return
		}
		var tail any
		if dec.Decode(&tail) != io.EOF {
			fail(w, 400, "request must contain one JSON object")
			return
		}
		if err := validate(&q); err != nil {
			fail(w, 400, err.Error())
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 25*time.Second)
		defer cancel()
		var vector []float64
		if q.Mode != "exact" {
			if embed == nil {
				fail(w, 503, "semantic model unavailable; choose exact mode or start the embedding service")
				return
			}
			var err error
			vector, err = embed(ctx, q.Query+". "+q.Profile)
			if err != nil {
				fail(w, 503, "semantic model unavailable or incompatible; exact mode remains available")
				return
			}
		}
		cutoff := threshold
		if q.MinScore != nil {
			cutoff = *q.MinScore
		}
		response, err := rank(ctx, c, q, vector, cutoff, time.Now())
		if err != nil {
			fail(w, 503, "search could not complete with the configured model")
			return
		}
		response.DurationMS = float64(time.Since(start).Microseconds()) / 1000
		response.Warnings = append(response.Warnings, "Scores measure retrieval similarity, not hiring probability. Skills absent from candidate text are not proof of missing ability.")
		send(w, 200, response)
	})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		origin := r.Header.Get("Origin")
		if includes([]string{"http://localhost:3000", "http://127.0.0.1:3000"}, origin) {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			w.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
		}
		if r.Method == "OPTIONS" {
			w.WriteHeader(204)
			return
		}
		mux.ServeHTTP(w, r)
	})
}
func loadCorpus(path string) (Corpus, error) {
	var c Corpus
	b, err := os.ReadFile(path)
	if err != nil {
		return c, err
	}
	if err = json.Unmarshal(b, &c); err != nil {
		return c, err
	}
	if len(c.Jobs) == 0 {
		return c, fmt.Errorf("corpus has no jobs")
	}
	seen := map[string]bool{}
	for _, j := range c.Jobs {
		if j.ID == "" || j.Title == "" || seen[j.ID] {
			return c, fmt.Errorf("missing or duplicate identity")
		}
		seen[j.ID] = true
		if c.Dimension > 0 {
			if len(j.Vector) != c.Dimension {
				return c, fmt.Errorf("job %s dimension mismatch", j.ID)
			}
			if _, err = cosine(j.Vector, j.Vector); err != nil {
				return c, err
			}
		}
	}
	return c, nil
}
func env(key, fallback string) string {
	if s := os.Getenv(key); s != "" {
		return s
	}
	return fallback
}
func main() {
	c, err := loadCorpus(env("NEXTROLE_DATA", "../data/demo.json"))
	if err != nil {
		log.Fatal(err)
	}
	threshold, err := strconv.ParseFloat(env("NEXTROLE_THRESHOLD", "0.40"), 64)
	if err != nil || threshold < 0 || threshold > 1 {
		log.Fatal("invalid NEXTROLE_THRESHOLD")
	}
	var embed Embedder
	if c.Dimension > 0 {
		embed = encoder(env("NEXTROLE_EMBED_URL", "http://127.0.0.1:8091"), c.Model, c.Revision)
	}
	server := &http.Server{Addr: env("NEXTROLE_ADDR", "127.0.0.1:8090"), Handler: handler(c, embed, threshold), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 30 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdown)
	}()
	log.Printf("NextRole listening on %s; %d vacancies; model %s", server.Addr, len(c.Jobs), c.Model)
	if err = server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
