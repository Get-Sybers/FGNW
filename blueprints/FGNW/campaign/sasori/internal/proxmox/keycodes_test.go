package proxmox

import "testing"

func TestCharToHMP_LowerCase(t *testing.T) {
	for _, tc := range []struct{ r rune; want string }{
		{'a', "a"}, {'z', "z"}, {'m', "m"},
	} {
		k, ok := charToHMP[tc.r]
		if !ok || k != tc.want {
			t.Errorf("charToHMP[%q] = %q, want %q", tc.r, k, tc.want)
		}
	}
}

func TestCharToHMP_UpperCase(t *testing.T) {
	for _, tc := range []struct{ r rune; want string }{
		{'A', "shift-a"}, {'Z', "shift-z"}, {'H', "shift-h"},
	} {
		k, ok := charToHMP[tc.r]
		if !ok || k != tc.want {
			t.Errorf("charToHMP[%q] = %q, want %q", tc.r, k, tc.want)
		}
	}
}

func TestCharToHMP_Whitespace(t *testing.T) {
	if k := charToHMP[' ']; k != "space" {
		t.Errorf("charToHMP[' '] = %q, want space", k)
	}
	if k := charToHMP['\n']; k != "ret" {
		t.Errorf("charToHMP['\\n'] = %q, want ret", k)
	}
	if k := charToHMP['\t']; k != "tab" {
		t.Errorf("charToHMP['\\t'] = %q, want tab", k)
	}
}

func TestCharToHMP_Symbols(t *testing.T) {
	for _, tc := range []struct{ r rune; want string }{
		{'.', "dot"}, {',', "comma"}, {'!', "shift-1"}, {'@', "shift-2"},
	} {
		k, ok := charToHMP[tc.r]
		if !ok || k != tc.want {
			t.Errorf("charToHMP[%q] = %q, want %q", tc.r, k, tc.want)
		}
	}
}

func TestTextToHMPKeys_Empty(t *testing.T) {
	if keys := textToHMPKeys(""); len(keys) != 0 {
		t.Errorf("textToHMPKeys(\"\") = %v, want empty", keys)
	}
}

func TestTextToHMPKeys_LowerCase(t *testing.T) {
	keys := textToHMPKeys("ab")
	if len(keys) != 2 || keys[0] != "a" || keys[1] != "b" {
		t.Errorf("textToHMPKeys(\"ab\") = %v, want [a b]", keys)
	}
}

func TestTextToHMPKeys_Mixed(t *testing.T) {
	keys := textToHMPKeys("Hi")
	if len(keys) != 2 || keys[0] != "shift-h" || keys[1] != "i" {
		t.Errorf("textToHMPKeys(\"Hi\") = %v, want [shift-h i]", keys)
	}
}

func TestTextToHMPKeys_SkipsUnknown(t *testing.T) {
	// Unicode rune with no HMP mapping should be silently skipped.
	keys := textToHMPKeys("aé")
	if len(keys) != 1 || keys[0] != "a" {
		t.Errorf("textToHMPKeys(\"aé\") = %v, want [a]", keys)
	}
}

func TestTypoKey_ReturnsDifferentKey(t *testing.T) {
	for _, k := range []string{"a", "s", "d", "f", "q", "w"} {
		n := typoKey(k)
		if n == k {
			t.Errorf("typoKey(%q) returned same key", k)
		}
		if n == "" {
			t.Errorf("typoKey(%q) returned empty string", k)
		}
	}
}

func TestTypoKey_UnknownFallsBack(t *testing.T) {
	n := typoKey("F5") // not in neighbours map
	if n == "" {
		t.Errorf("typoKey(\"F5\") returned empty string, want fallback")
	}
}
