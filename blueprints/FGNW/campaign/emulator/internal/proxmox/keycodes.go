package proxmox

import (
	"math"
	"math/rand"
	"time"
)

// textToHMPKeys converts a plain-text string into a slice of HMP sendkey
// key names (US QWERTY layout).  Multi-byte runes that have no direct key
// mapping are silently skipped.
func textToHMPKeys(s string) []string {
	out := make([]string, 0, len(s))
	for _, r := range s {
		if k, ok := charToHMP[r]; ok {
			out = append(out, k)
		}
	}
	return out
}

// typoKey returns a plausible neighbouring key for a typo — always returns a
// different key from the input so the backspace correction makes sense.
func typoKey(hmpKey string) string {
	// Return a neighbour from the same row; fall back to "x" for unknowns.
	neighbours := map[string]string{
		"a": "s", "s": "d", "d": "f", "f": "g", "g": "h", "h": "j",
		"j": "k", "k": "l", "q": "w", "w": "e", "e": "r", "r": "t",
		"z": "x", "x": "c", "c": "v", "v": "b", "b": "n", "n": "m",
	}
	if n, ok := neighbours[hmpKey]; ok {
		return n
	}
	return "x"
}

// logNormalDelay returns a duration drawn from a log-normal distribution whose
// median is meanMs milliseconds and whose sigma (in log-space) gives ~40%
// coefficient of variation — realistic inter-keystroke timing.
func logNormalDelay(meanMs float64) time.Duration {
	const sigma = 0.4 // log-space std dev
	mu := math.Log(meanMs) - (sigma*sigma)/2
	sample := math.Exp(mu + sigma*rand.NormFloat64())
	if sample < 20 {
		sample = 20 // floor at 20 ms
	}
	return time.Duration(sample) * time.Millisecond
}

// charToHMP maps Unicode runes to their HMP sendkey key name (US QWERTY).
var charToHMP = map[rune]string{
	// Lowercase letters
	'a': "a", 'b': "b", 'c': "c", 'd': "d", 'e': "e",
	'f': "f", 'g': "g", 'h': "h", 'i': "i", 'j': "j",
	'k': "k", 'l': "l", 'm': "m", 'n': "n", 'o': "o",
	'p': "p", 'q': "q", 'r': "r", 's': "s", 't': "t",
	'u': "u", 'v': "v", 'w': "w", 'x': "x", 'y': "y",
	'z': "z",
	// Uppercase letters
	'A': "shift-a", 'B': "shift-b", 'C': "shift-c", 'D': "shift-d",
	'E': "shift-e", 'F': "shift-f", 'G': "shift-g", 'H': "shift-h",
	'I': "shift-i", 'J': "shift-j", 'K': "shift-k", 'L': "shift-l",
	'M': "shift-m", 'N': "shift-n", 'O': "shift-o", 'P': "shift-p",
	'Q': "shift-q", 'R': "shift-r", 'S': "shift-s", 'T': "shift-t",
	'U': "shift-u", 'V': "shift-v", 'W': "shift-w", 'X': "shift-x",
	'Y': "shift-y", 'Z': "shift-z",
	// Digits
	'0': "0", '1': "1", '2': "2", '3': "3", '4': "4",
	'5': "5", '6': "6", '7': "7", '8': "8", '9': "9",
	// Symbols (US QWERTY, unshifted)
	'-': "minus", '=': "equal", '[': "bracket_left", ']': "bracket_right",
	'\\': "backslash", ';': "semicolon", '\'': "apostrophe",
	'`': "grave_accent", ',': "comma", '.': "dot", '/': "slash",
	// Symbols (shifted)
	'!': "shift-1", '@': "shift-2", '#': "shift-3", '$': "shift-4",
	'%': "shift-5", '^': "shift-6", '&': "shift-7", '*': "shift-8",
	'(': "shift-9", ')': "shift-0", '_': "shift-minus", '+': "shift-equal",
	'{': "shift-bracket_left", '}': "shift-bracket_right",
	'|': "shift-backslash", ':': "shift-semicolon", '"': "shift-apostrophe",
	'~': "shift-grave_accent", '<': "shift-comma", '>': "shift-dot",
	'?': "shift-slash",
	// Whitespace / control
	' ':  "space",
	'\t': "tab",
	'\n': "ret",
}
