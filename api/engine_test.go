package main

import (
	"context"
	"math"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestCosine(t *testing.T) {
	for _, tc := range []struct {
		name string
		a, b []float64
		want float64
		bad  bool
	}{
		{"same", []float64{1, 2}, []float64{1, 2}, 1, false},
		{"orthogonal", []float64{1, 0}, []float64{0, 1}, 0, false},
		{"opposite", []float64{1, 0}, []float64{-1, 0}, -1, false},
		{"dimensions", []float64{1}, []float64{1, 0}, 0, true},
		{"empty", nil, nil, 0, true}, {"zero", []float64{0}, []float64{1}, 0, true},
		{"nan", []float64{math.NaN()}, []float64{1}, 0, true},
		{"infinite", []float64{1}, []float64{math.Inf(1)}, 0, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			v, e := cosine(tc.a, tc.b)
			if (e != nil) != tc.bad || (!tc.bad && math.Abs(v-tc.want) > 1e-10) {
				t.Fatalf("%v %v", v, e)
			}
		})
	}
}
func TestPhrase(t *testing.T) {
	for _, tc := range []struct {
		text, query string
		want        bool
	}{
		{"Senior Software Engineer", "software engineer", true},
		{"Software Engineering", "software engineer", false},
		{"Flutter/Developer", "flutter developer", true},
		{"مهندس برمجيات أول", "مهندس", true},
		{"مهندسون", "مهندس", false},
		{"SuperReact Developer", "React", false},
		{"C++ Developer", "C++", true}, {"C# Developer", "C++", false},
		{"Senior Developer", "", false},
	} {
		t.Run(tc.text+tc.query, func(t *testing.T) {
			if phrase(tc.text, tc.query) != tc.want {
				t.Fatal("wrong boundary")
			}
		})
	}
}
func fixture() Corpus {
	return Corpus{Dataset: "unit", Model: "fixture", Dimension: 2, Jobs: []Job{
		{ID: "a", Title: "Flutter Developer", Company: "One", Location: "Dubai", Country: "AE", WorkMode: "remote", JobType: "full_time", Vector: []float64{1, 0}, Skills: []string{"Flutter", "Dart"}},
		{ID: "b", Title: "Mobile Engineer", Company: "Two", Country: "GB", Vector: []float64{0.8, 0.6}},
		{ID: "c", Title: "Nurse", Company: "Three", Vector: []float64{0, 1}},
		{ID: "d", Title: "Flutter Developer", Company: "One", Location: "Dubai", Country: "AE", WorkMode: "remote", JobType: "full_time", Vector: []float64{1, 0}},
	}}
}
func TestRankingModes(t *testing.T) {
	for _, tc := range []struct {
		mode  string
		count int
	}{{"exact", 1}, {"semantic", 2}, {"hybrid", 2}} {
		t.Run(tc.mode, func(t *testing.T) {
			r := Request{Query: "Flutter Developer", Profile: "Flutter", Mode: tc.mode}
			_ = validate(&r)
			out, err := rank(context.Background(), fixture(), r, []float64{1, 0}, 0.7, time.Now())
			if err != nil || out.Total != tc.count || out.Results[0].ID != "a" {
				t.Fatalf("%+v %v", out, err)
			}
		})
	}
}
func TestFiltersAndPagination(t *testing.T) {
	r := Request{Query: "Flutter Developer", Countries: []string{"AE"}, WorkMode: "remote", PageSize: 1}
	_ = validate(&r)
	out, _ := rank(context.Background(), fixture(), r, []float64{1, 0}, 0.7, time.Now())
	if out.Total != 1 || out.HasMore {
		t.Fatal(out)
	}
	r.Countries = nil
	r.WorkMode = ""
	out, _ = rank(context.Background(), fixture(), r, []float64{1, 0}, 0.7, time.Now())
	if out.Total != 2 || !out.HasMore {
		t.Fatal(out)
	}
	r.Page = 2
	out, _ = rank(context.Background(), fixture(), r, []float64{1, 0}, 0.7, time.Now())
	if out.Results[0].ID != "b" || out.HasMore {
		t.Fatal(out)
	}
	r.Page = 99
	out, _ = rank(context.Background(), fixture(), r, []float64{1, 0}, 0.7, time.Now())
	if len(out.Results) != 0 {
		t.Fatal(out)
	}
}
func TestExclusionsAndAge(t *testing.T) {
	r := Request{ExcludedCompanies: []string{"one"}}
	if allowed(fixture().Jobs[0], r, time.Now()) {
		t.Fatal("company filter")
	}
	r = Request{MaxAgeDays: 7}
	if allowed(fixture().Jobs[0], r, time.Now()) {
		t.Fatal("unknown date is not recent")
	}
}
func TestCancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	r := Request{Query: "a", Mode: "exact", Page: 1, PageSize: 10}
	if _, err := rank(ctx, fixture(), r, nil, 0.4, time.Now()); err == nil {
		t.Fatal("expected cancellation")
	}
}
func TestAPIContract(t *testing.T) {
	h := handler(fixture(), func(context.Context, string) ([]float64, error) { return []float64{1, 0}, nil }, 0.7)
	for _, tc := range []struct {
		name, body string
		status     int
	}{
		{"valid", `{"query":"Flutter Developer"}`, 200},
		{"empty", `{"query":" "}`, 400},
		{"bad_mode", `{"query":"x","mode":"magic"}`, 400},
		{"page", `{"query":"x","page_size":51}`, 400},
		{"threshold", `{"query":"x","min_score":97}`, 400},
		{"unknown", `{"query":"x","secret":"x"}`, 400},
		{"trailing", `{"query":"x"} {}`, 400},
		{"json", `{`, 400},
	} {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest("POST", "/api/v1/search", strings.NewReader(tc.body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			h.ServeHTTP(w, req)
			if w.Code != tc.status {
				t.Fatalf("%d %s", w.Code, w.Body.String())
			}
			if strings.Contains(w.Body.String(), `"embedding"`) {
				t.Fatal("vectors leaked")
			}
		})
	}
}
func TestSemanticUnavailable(t *testing.T) {
	h := handler(fixture(), nil, 0.4)
	r := httptest.NewRequest("POST", "/api/v1/search", strings.NewReader(`{"query":"Flutter"}`))
	r.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 503 {
		t.Fatal(w.Code)
	}
}
func TestSkillEvidence(t *testing.T) {
	r := Request{Query: "Flutter Developer", Profile: "I know Flutter", Mode: "exact"}
	_ = validate(&r)
	out, _ := rank(context.Background(), fixture(), r, nil, 0.4, time.Now())
	if len(out.Results[0].MatchedSkills) != 1 || len(out.Results[0].MissingSkills) != 1 {
		t.Fatal(out)
	}
}
func BenchmarkRank10000(b *testing.B) {
	c := fixture()
	base := c.Jobs
	c.Jobs = nil
	for i := 0; i < 2500; i++ {
		c.Jobs = append(c.Jobs, base...)
	}
	r := Request{Query: "Flutter Developer", Mode: "hybrid", Page: 1, PageSize: 10}
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = rank(context.Background(), c, r, []float64{1, 0}, 0.7, time.Now())
	}
}
