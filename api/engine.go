package main

import (
	"context"
	"errors"
	"math"
	"sort"
	"strings"
	"sync"
	"time"
	"unicode"
)

type Job struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Company     string    `json:"company"`
	Location    string    `json:"location"`
	Country     string    `json:"country"`
	Source      string    `json:"source"`
	URL         string    `json:"url"`
	Description string    `json:"description"`
	WorkMode    string    `json:"work_mode"`
	JobType     string    `json:"job_type"`
	PostedAt    time.Time `json:"posted_at"`
	Skills      []string  `json:"skills"`
	Vector      []float64 `json:"embedding,omitempty"`
}
type Corpus struct {
	Dataset     string `json:"dataset"`
	CollectedAt string `json:"collected_at"`
	Model       string `json:"model"`
	Revision    string `json:"revision"`
	Dimension   int    `json:"dimension"`
	Jobs        []Job  `json:"jobs"`
}
type Request struct {
	Query             string   `json:"query"`
	Profile           string   `json:"profile,omitempty"`
	Countries         []string `json:"countries,omitempty"`
	Sources           []string `json:"sources,omitempty"`
	WorkMode          string   `json:"work_mode,omitempty"`
	JobType           string   `json:"job_type,omitempty"`
	ExcludedCompanies []string `json:"excluded_companies,omitempty"`
	Mode              string   `json:"mode,omitempty"`
	MinScore          *float64 `json:"min_score,omitempty"`
	Page              int      `json:"page,omitempty"`
	PageSize          int      `json:"page_size,omitempty"`
	MaxAgeDays        int      `json:"max_age_days,omitempty"`
}
type Result struct {
	Job
	Score         float64  `json:"score"`
	MatchType     string   `json:"match_type"`
	Explanation   string   `json:"explanation"`
	MatchedSkills []string `json:"matched_skills"`
	MissingSkills []string `json:"missing_skills"`
}
type Response struct {
	Results    []Result `json:"results"`
	Total      int      `json:"total_count"`
	Page       int      `json:"page"`
	PageSize   int      `json:"page_size"`
	HasMore    bool     `json:"has_more"`
	Mode       string   `json:"mode"`
	Model      string   `json:"model"`
	Threshold  float64  `json:"threshold"`
	Dataset    string   `json:"dataset"`
	DurationMS float64  `json:"duration_ms"`
	Warnings   []string `json:"warnings"`
}

// Adapted from the author's prior matching helper.
func cosine(a, b []float64) (float64, error) {
	if len(a) == 0 || len(a) != len(b) {
		return 0, errors.New("embedding dimensions must match and be nonempty")
	}
	var dot, aa, bb float64
	for i, v := range a {
		if math.IsNaN(v) || math.IsInf(v, 0) || math.IsNaN(b[i]) || math.IsInf(b[i], 0) {
			return 0, errors.New("embedding contains non-finite values")
		}
		dot += v * b[i]
		aa += v * v
		bb += b[i] * b[i]
	}
	if aa == 0 || bb == 0 {
		return 0, errors.New("embedding norm must be positive")
	}
	denom := math.Sqrt(aa) * math.Sqrt(bb)
	value := dot / denom
	if math.IsNaN(value) || math.IsInf(value, 0) {
		return 0, errors.New("embedding overflow")
	}
	return math.Max(-1, math.Min(1, value)), nil
}

// Retain letters/numbers in every script; punctuation separates phrases.
func normalise(s string) string {
	return strings.Join(strings.FieldsFunc(strings.ToLower(s), func(r rune) bool {
		return !unicode.IsLetter(r) && !unicode.IsNumber(r) && !unicode.IsMark(r) && r != '+' && r != '#'
	}), " ")
}
func phrase(text, query string) bool {
	t, q := normalise(text), normalise(query)
	return q != "" && strings.Contains(" "+t+" ", " "+q+" ")
}
func includes(values []string, value string) bool {
	if len(values) == 0 {
		return true
	}
	for _, v := range values {
		if strings.EqualFold(v, value) {
			return true
		}
	}
	return false
}
func validate(r *Request) error {
	r.Query = strings.TrimSpace(r.Query)
	r.Profile = strings.TrimSpace(r.Profile)
	if normalise(r.Query) == "" {
		return errors.New("enter a role or skill query")
	}
	if len([]rune(r.Query)) > 200 || len([]rune(r.Profile)) > 6000 {
		return errors.New("query exceeds 200 or candidate text exceeds 6000 characters")
	}
	if r.Mode == "" {
		r.Mode = "hybrid"
	}
	if !includes([]string{"hybrid", "exact", "semantic"}, r.Mode) {
		return errors.New("mode must be exact, semantic or hybrid")
	}
	if r.Page == 0 {
		r.Page = 1
	}
	if r.PageSize == 0 {
		r.PageSize = 10
	}
	if r.Page < 1 || r.Page > 100000 || r.PageSize < 1 || r.PageSize > 50 {
		return errors.New("page must be 1–100000 and page_size 1–50")
	}
	if r.MinScore != nil && (*r.MinScore < 0 || *r.MinScore > 1 || math.IsNaN(*r.MinScore)) {
		return errors.New("min_score must be between 0 and 1")
	}
	if r.MaxAgeDays < 0 || r.MaxAgeDays > 3650 {
		return errors.New("max_age_days must be 0–3650")
	}
	if r.WorkMode != "" && !includes([]string{"remote", "hybrid", "onsite"}, r.WorkMode) {
		return errors.New("invalid work_mode")
	}
	if r.JobType != "" && !includes([]string{"full_time", "part_time", "contract", "internship"}, r.JobType) {
		return errors.New("invalid job_type")
	}
	return nil
}
func allowed(j Job, r Request, now time.Time) bool {
	if !includes(r.Countries, j.Country) || !includes(r.Sources, j.Source) {
		return false
	}
	if r.WorkMode != "" && r.WorkMode != j.WorkMode {
		return false
	}
	if r.JobType != "" && r.JobType != j.JobType {
		return false
	}
	for _, c := range r.ExcludedCompanies {
		if normalise(c) == normalise(j.Company) {
			return false
		}
	}
	if r.MaxAgeDays > 0 && (j.PostedAt.IsZero() || j.PostedAt.Before(now.AddDate(0, 0, -r.MaxAgeDays))) {
		return false
	}
	return true
}
func dedupeKey(j Job) string {
	if normalise(j.Title) == "" || normalise(j.Company) == "" {
		return "id:" + j.ID
	}
	return normalise(j.Title) + "|" + normalise(j.Company) + "|" + normalise(j.Location)
}
func better(a, b Result) bool {
	if a.Score != b.Score {
		return a.Score > b.Score
	}
	if !a.PostedAt.Equal(b.PostedAt) {
		return a.PostedAt.After(b.PostedAt)
	}
	return a.ID < b.ID
}
func rank(ctx context.Context, c Corpus, r Request, q []float64, threshold float64, now time.Time) (Response, error) {
	start := time.Now()
	resp := Response{Results: []Result{}, Page: r.Page, PageSize: r.PageSize, Mode: r.Mode, Model: c.Model, Threshold: threshold, Dataset: c.Dataset, Warnings: []string{}}
	if r.Mode != "exact" {
		if _, err := cosine(q, q); err != nil {
			return resp, err
		}
		if len(q) != c.Dimension {
			return resp, errors.New("query embedding model dimension mismatch")
		}
	}
	jobs := make(chan Job)
	out := make(chan Result)
	var wg sync.WaitGroup
	for w := 0; w < 8; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobs {
				if ctx.Err() != nil {
					return
				}
				if !allowed(j, r, now) {
					continue
				}
				score, route, explanation := 0.0, "", ""
				if r.Mode != "semantic" && phrase(j.Title, r.Query) {
					score = 1
					route = "exact"
					explanation = "The role query is a complete phrase in this vacancy title."
				} else if r.Mode != "exact" {
					v, err := cosine(q, j.Vector)
					if err != nil || v < threshold {
						continue
					}
					score = v
					route = "semantic"
					explanation = "The query and candidate text are similar to the vacancy text in the recorded embedding model."
				} else {
					continue
				}
				matched, missing := []string{}, []string{}
				for _, skill := range j.Skills {
					if phrase(r.Query+" "+r.Profile, skill) {
						matched = append(matched, skill)
					} else {
						missing = append(missing, skill)
					}
				}
				j.Vector = nil
				result := Result{Job: j, Score: score, MatchType: route, Explanation: explanation, MatchedSkills: matched, MissingSkills: missing}
				select {
				case out <- result:
				case <-ctx.Done():
					return
				}
			}
		}()
	}
	go func() {
		defer close(jobs)
		for _, j := range c.Jobs {
			select {
			case jobs <- j:
			case <-ctx.Done():
				return
			}
		}
	}()
	go func() { wg.Wait(); close(out) }()
	best := map[string]Result{}
	for result := range out {
		k := dedupeKey(result.Job)
		old, ok := best[k]
		if !ok || better(result, old) {
			best[k] = result
		}
	}
	if ctx.Err() != nil {
		return resp, ctx.Err()
	}
	results := make([]Result, 0, len(best))
	for _, v := range best {
		results = append(results, v)
	}
	sort.Slice(results, func(i, j int) bool { return better(results[i], results[j]) })
	resp.Total = len(results)
	offset := (r.Page - 1) * r.PageSize
	if offset < len(results) {
		end := min(offset+r.PageSize, len(results))
		resp.Results = results[offset:end]
		resp.HasMore = end < len(results)
	}
	resp.DurationMS = float64(time.Since(start).Microseconds()) / 1000
	return resp, nil
}
