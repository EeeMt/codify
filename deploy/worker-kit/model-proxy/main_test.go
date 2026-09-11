package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"testing"
	"time"
)

type goldenVectors struct {
	ReservedRequestFields  []string            `json:"reserved_request_fields"`
	MergeCases             []goldenMergeCase   `json:"merge_cases"`
	ReservedRejectionCases []goldenRejection   `json:"reserved_rejection_cases"`
	InvalidOptionsCases    []goldenInvalidCase `json:"invalid_options_cases"`
}

type goldenMergeCase struct {
	Name     string         `json:"name"`
	Body     map[string]any `json:"body"`
	Options  map[string]any `json:"options"`
	Expected map[string]any `json:"expected"`
}

type goldenRejection struct {
	Name    string         `json:"name"`
	Options map[string]any `json:"options"`
	Fields  []string       `json:"fields"`
}

type goldenInvalidCase struct {
	Name    string `json:"name"`
	Options any    `json:"options"`
}

func loadGoldenVectors(t *testing.T) goldenVectors {
	t.Helper()
	path := filepath.Join("testdata", "golden_vectors.json")
	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read golden vectors: %v", err)
	}
	var vectors goldenVectors
	if err := json.Unmarshal(payload, &vectors); err != nil {
		t.Fatalf("decode golden vectors: %v", err)
	}
	return vectors
}

// decodeNumbers re-decodes a JSON fragment with UseNumber so expectations
// compare exactly like the merge output.
func decodeNumbers(t *testing.T, value any) any {
	t.Helper()
	payload, err := json.Marshal(value)
	if err != nil {
		t.Fatalf("marshal fragment: %v", err)
	}
	decoded, err := decodeJSONObject(payload)
	if err != nil {
		t.Fatalf("decode fragment: %v", err)
	}
	return decoded
}

func TestMergeMatchesSharedGoldenVectors(t *testing.T) {
	vectors := loadGoldenVectors(t)
	if len(vectors.MergeCases) == 0 {
		t.Fatal("golden vectors contain no merge cases")
	}
	for _, testCase := range vectors.MergeCases {
		t.Run(testCase.Name, func(t *testing.T) {
			body := decodeNumbers(t, testCase.Body).(map[string]any)
			options := decodeNumbers(t, testCase.Options).(map[string]any)
			expected := decodeNumbers(t, testCase.Expected).(map[string]any)
			merged := mergeProviderOptions(body, options)
			if !reflect.DeepEqual(merged, expected) {
				t.Fatalf("merged body mismatch:\n got: %#v\nwant: %#v", merged, expected)
			}
			if !reflect.DeepEqual(body, decodeNumbers(t, testCase.Body).(map[string]any)) {
				t.Fatal("merge mutated the base body")
			}
		})
	}
}

func TestReservedFieldSetMatchesGoldenVectors(t *testing.T) {
	vectors := loadGoldenVectors(t)
	declared := append([]string(nil), vectors.ReservedRequestFields...)
	sort.Strings(declared)
	implemented := make([]string, 0, len(reservedRequestFields))
	for key := range reservedRequestFields {
		implemented = append(implemented, key)
	}
	sort.Strings(implemented)
	if !reflect.DeepEqual(declared, implemented) {
		t.Fatalf("reserved field set drifted: golden=%v implementation=%v", declared, implemented)
	}
}

func TestReservedOptionsAreNeverMergedInGoldenVectors(t *testing.T) {
	vectors := loadGoldenVectors(t)
	for _, testCase := range vectors.ReservedRejectionCases {
		if len(testCase.Fields) != 0 {
			continue
		}
		t.Run(testCase.Name, func(t *testing.T) {
			body := decodeNumbers(t, map[string]any{"model": "qwen3"}).(map[string]any)
			merged := mergeProviderOptions(body, decodeNumbers(t, testCase.Options).(map[string]any))
			if merged["model"] != "qwen3" {
				t.Fatalf("reserved field was merged: %#v", merged["model"])
			}
		})
	}
}

func TestLoadConfigRejectsInvalidOptions(t *testing.T) {
	vectors := loadGoldenVectors(t)
	for _, testCase := range vectors.InvalidOptionsCases {
		t.Run(testCase.Name, func(t *testing.T) {
			payload, err := json.Marshal(testCase.Options)
			if err != nil {
				t.Fatalf("marshal options: %v", err)
			}
			directory := t.TempDir()
			optionsPath := filepath.Join(directory, "options.json")
			if err := os.WriteFile(optionsPath, payload, 0o600); err != nil {
				t.Fatalf("write options: %v", err)
			}
			if _, err := loadConfig(
				"127.0.0.1:0",
				"https://provider.example/api/v1",
				"anthropic_messages",
				optionsPath,
				filepath.Join(directory, "readiness.json"),
			); err == nil {
				t.Fatal("expected non-object provider_options to be rejected")
			}
		})
	}
}

func TestLoadConfigRejectsUnknownProtocolAndScheme(t *testing.T) {
	directory := t.TempDir()
	readiness := filepath.Join(directory, "readiness.json")
	if _, err := loadConfig("127.0.0.1:0", "https://provider.example", "vendor_proprietary", "", readiness); err == nil {
		t.Fatal("expected unknown protocol to be rejected")
	}
	if _, err := loadConfig("127.0.0.1:0", "ftp://provider.example", "anthropic_messages", "", readiness); err == nil {
		t.Fatal("expected unsupported upstream scheme to be rejected")
	}
}

func testProxy(t *testing.T, protocol string, options map[string]any, upstreamURL string) *httptest.Server {
	t.Helper()
	parsed, err := url.Parse(upstreamURL)
	if err != nil {
		t.Fatalf("parse upstream: %v", err)
	}
	suffix, ok := targetPathSuffix[protocol]
	if !ok {
		t.Fatalf("unknown protocol %s", protocol)
	}
	if options == nil {
		options = map[string]any{}
	}
	handler, err := newProxy(&config{
		upstream:   parsed,
		protocol:   protocol,
		options:    options,
		pathSuffix: suffix,
	})
	if err != nil {
		t.Fatalf("newProxy: %v", err)
	}
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)
	return server
}

func TestProxyMergesTargetRequestAndPreservesHeaders(t *testing.T) {
	recorded := make(chan *http.Request, 1)
	recordedBody := make(chan []byte, 1)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		payload, _ := io.ReadAll(r.Body)
		recorded <- r.Clone(context.Background())
		recordedBody <- payload
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer upstream.Close()

	proxy := testProxy(t, "anthropic_messages", map[string]any{
		"temperature":          0.6,
		"chat_template_kwargs": map[string]any{"thinking": true, "reasoning_effort": "high"},
	}, upstream.URL+"/api/v1")

	body := `{"model":"qwen3","stream":true,"messages":[{"role":"user","content":"hello"}],"chat_template_kwargs":{"reasoning_effort":"medium"}}`
	request, err := http.NewRequest(http.MethodPost, proxy.URL+"/api/v1/messages", bytes.NewReader([]byte(body)))
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Authorization", "Bearer test-key")

	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("proxy request: %v", err)
	}
	defer response.Body.Close()
	responseBody, _ := io.ReadAll(response.Body)

	if response.StatusCode != 201 {
		t.Fatalf("upstream status not preserved: %d", response.StatusCode)
	}
	if string(responseBody) != `{"ok":true}` {
		t.Fatalf("upstream body not preserved: %s", responseBody)
	}

	upstreamRequest := <-recorded
	upstreamPayload := <-recordedBody
	if upstreamRequest.URL.Path != "/api/v1/messages" {
		t.Fatalf("upstream path not preserved: %s", upstreamRequest.URL.Path)
	}
	if upstreamRequest.Header.Get("Authorization") != "Bearer test-key" {
		t.Fatalf("authorization header not preserved: %s", upstreamRequest.Header.Get("Authorization"))
	}
	if upstreamRequest.Header.Get("Content-Encoding") != "" {
		t.Fatalf("unexpected content-encoding: %s", upstreamRequest.Header.Get("Content-Encoding"))
	}
	if upstreamRequest.ContentLength != int64(len(upstreamPayload)) {
		t.Fatalf("content-length not recomputed: %d != %d", upstreamRequest.ContentLength, len(upstreamPayload))
	}
	var merged map[string]any
	if err := json.Unmarshal(upstreamPayload, &merged); err != nil {
		t.Fatalf("upstream body is not JSON: %v", err)
	}
	if merged["temperature"] != 0.6 {
		t.Fatalf("provider option absent: %#v", merged["temperature"])
	}
	kwargs := merged["chat_template_kwargs"].(map[string]any)
	if kwargs["thinking"] != true || kwargs["reasoning_effort"] != "high" {
		t.Fatalf("recursive merge failed: %#v", kwargs)
	}
	if merged["stream"] != true {
		t.Fatalf("harness stream flag was modified: %#v", merged["stream"])
	}
	if merged["model"] != "qwen3" {
		t.Fatalf("harness model was modified: %#v", merged["model"])
	}
}

func TestProxyForwardsNonTargetRequestsUntouched(t *testing.T) {
	recordedBody := make(chan []byte, 1)
	recordedPath := make(chan string, 1)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		payload, _ := io.ReadAll(r.Body)
		recordedBody <- payload
		recordedPath <- r.URL.Path
		w.WriteHeader(200)
	}))
	defer upstream.Close()

	proxy := testProxy(t, "openai_responses", map[string]any{"temperature": 0.6}, upstream.URL+"/api/v1")
	body := `{"model":"qwen3","input":"hello"}`
	request, _ := http.NewRequest(http.MethodPost, proxy.URL+"/api/v1/models", bytes.NewReader([]byte(body)))
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("proxy request: %v", err)
	}
	defer response.Body.Close()
	_, _ = io.ReadAll(response.Body)

	if string(<-recordedBody) != body {
		t.Fatalf("non-target body was modified")
	}
	if <-recordedPath != "/api/v1/models" {
		t.Fatalf("non-target path was modified")
	}
}

func TestProxyFailsClosed(t *testing.T) {
	upstreamCalls := make(chan struct{}, 4)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		upstreamCalls <- struct{}{}
		w.WriteHeader(200)
	}))
	defer upstream.Close()

	proxy := testProxy(t, "openai_chat_completions", map[string]any{"temperature": 0.6}, upstream.URL+"/v1")

	cases := []struct {
		name        string
		body        string
		encoding    string
		expectedErr string
	}{
		{name: "non_json_body", body: "not json", expectedErr: errorCodeNonJSON},
		{name: "json_array_body", body: `[1,2,3]`, expectedErr: errorCodeNonJSON},
		{name: "compressed_body", body: `{"model":"qwen3"}`, encoding: "gzip", expectedErr: errorCodeCompressed},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			request, _ := http.NewRequest(http.MethodPost, proxy.URL+"/v1/chat/completions", bytes.NewReader([]byte(testCase.body)))
			if testCase.encoding != "" {
				request.Header.Set("Content-Encoding", testCase.encoding)
			}
			response, err := http.DefaultClient.Do(request)
			if err != nil {
				t.Fatalf("proxy request: %v", err)
			}
			defer response.Body.Close()
			payload, _ := io.ReadAll(response.Body)
			if response.StatusCode != http.StatusBadGateway {
				t.Fatalf("expected 502, got %d", response.StatusCode)
			}
			var failure struct {
				Error struct {
					Type string `json:"type"`
					Code string `json:"code"`
				} `json:"error"`
			}
			if err := json.Unmarshal(payload, &failure); err != nil {
				t.Fatalf("error body is not JSON: %v (%s)", err, payload)
			}
			if failure.Error.Type != errorTypeCodifyProxy || failure.Error.Code != testCase.expectedErr {
				t.Fatalf("unexpected proxy error: %s", payload)
			}
		})
	}
	select {
	case <-upstreamCalls:
		t.Fatal("fail-closed request reached the upstream")
	default:
	}
}

func TestProxyStreamsSSEWithoutWaitingForCompletion(t *testing.T) {
	release := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		_, _ = w.Write([]byte("data: first\n\n"))
		if flusher, ok := w.(http.Flusher); ok {
			flusher.Flush()
		}
		<-release
		_, _ = w.Write([]byte("data: second\n\n"))
	}))
	defer upstream.Close()
	defer close(release)

	proxy := testProxy(t, "anthropic_messages", map[string]any{"temperature": 0.6}, upstream.URL+"/api/v1")
	request, _ := http.NewRequest(http.MethodPost, proxy.URL+"/api/v1/messages", bytes.NewReader([]byte(`{"model":"qwen3","stream":true,"messages":[]}`)))
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("proxy request: %v", err)
	}
	defer response.Body.Close()

	firstChunk := make(chan string, 1)
	go func() {
		buffer := make([]byte, 13)
		n, _ := io.ReadFull(response.Body, buffer)
		firstChunk <- string(buffer[:n])
	}()

	select {
	case chunk := <-firstChunk:
		if chunk != "data: first\n\n" {
			t.Fatalf("unexpected first chunk: %q", chunk)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("first SSE chunk was buffered until the response completed")
	}
}

func TestProxyCancellationPropagatesUpstream(t *testing.T) {
	upstreamStarted := make(chan struct{})
	upstreamCancelled := make(chan struct{})
	release := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// An upstream reads the request body, which is also what lets the Go
		// server detect the client disconnect and cancel r.Context().
		_, _ = io.Copy(io.Discard, r.Body)
		close(upstreamStarted)
		select {
		case <-r.Context().Done():
			close(upstreamCancelled)
		case <-release:
		}
	}))
	defer upstream.Close()
	// Registered last so it unwinds first and never leaves the upstream
	// handler blocked if cancellation was not observed.
	defer close(release)

	proxy := testProxy(t, "openai_responses", map[string]any{"temperature": 0.6}, upstream.URL+"/api/v1")

	ctx, cancel := context.WithCancel(context.Background())
	request, _ := http.NewRequestWithContext(ctx, http.MethodPost, proxy.URL+"/api/v1/responses", bytes.NewReader([]byte(`{"model":"qwen3","input":"hi"}`)))
	go func() {
		response, err := http.DefaultClient.Do(request)
		if err == nil {
			_ = response.Body.Close()
		}
	}()

	select {
	case <-upstreamStarted:
	case <-time.After(3 * time.Second):
		t.Fatal("upstream request never started")
	}
	cancel()
	select {
	case <-upstreamCancelled:
	case <-time.After(3 * time.Second):
		t.Fatal("client cancellation did not cancel the upstream request")
	}
}

func TestProxyPreservesUpstreamErrorResponse(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(429)
		_, _ = w.Write([]byte(`{"error":"rate limited"}`))
	}))
	defer upstream.Close()

	proxy := testProxy(t, "anthropic_messages", map[string]any{"temperature": 0.6}, upstream.URL+"/api/v1")
	request, _ := http.NewRequest(http.MethodPost, proxy.URL+"/api/v1/messages", bytes.NewReader([]byte(`{"model":"qwen3","stream":true,"messages":[]}`)))
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatalf("proxy request: %v", err)
	}
	defer response.Body.Close()
	payload, _ := io.ReadAll(response.Body)
	if response.StatusCode != 429 || string(payload) != `{"error":"rate limited"}` {
		t.Fatalf("upstream error not preserved: %d %s", response.StatusCode, payload)
	}
}

func TestWriteReadinessIsAtomic(t *testing.T) {
	directory := t.TempDir()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer listener.Close()

	readinessPath := filepath.Join(directory, "nested", "model-proxy-readiness.json")
	cfg := &config{protocol: "anthropic_messages", readinessPath: readinessPath}
	if err := writeReadiness(cfg, listener); err != nil {
		t.Fatalf("writeReadiness: %v", err)
	}
	payload, err := os.ReadFile(readinessPath)
	if err != nil {
		t.Fatalf("read readiness: %v", err)
	}
	var readiness map[string]any
	if err := json.Unmarshal(payload, &readiness); err != nil {
		t.Fatalf("readiness is not JSON: %v", err)
	}
	if readiness["schema"] != readinessSchema {
		t.Fatalf("unexpected readiness schema: %#v", readiness["schema"])
	}
	if readiness["listen"] != listener.Addr().String() {
		t.Fatalf("unexpected readiness listen: %#v", readiness["listen"])
	}
	if _, err := os.Stat(readinessPath + ".tmp"); !os.IsNotExist(err) {
		t.Fatal("temporary readiness file was left behind")
	}
}
