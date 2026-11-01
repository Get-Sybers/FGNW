package activity

import (
	"math/rand"
	"sync"
)

// Package-level seeded RNG protected by a mutex so multiple goroutines can
// call randIntn() safely.
var (
	rngMu  sync.Mutex
	rngSrc = rand.New(rand.NewSource(rand.Int63()))
)

func randIntn(n int) int {
	rngMu.Lock()
	defer rngMu.Unlock()
	return rngSrc.Intn(n)
}

func randFloat64() float64 {
	rngMu.Lock()
	defer rngMu.Unlock()
	return rngSrc.Float64()
}
