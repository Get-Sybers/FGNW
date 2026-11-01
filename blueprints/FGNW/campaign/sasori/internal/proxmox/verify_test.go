package proxmox

import "testing"

func TestVerifyResult_Pass_Full(t *testing.T) {
	r := VerifyResult{VMFound: true, VMRunning: true, QGAOK: true, SendKeyOK: true}
	if !r.Pass() {
		t.Error("fully-set result should pass")
	}
}

func TestVerifyResult_Pass_MissingQGA(t *testing.T) {
	r := VerifyResult{VMFound: true, VMRunning: true, QGAOK: false, SendKeyOK: true}
	if r.Pass() {
		t.Error("result with QGAOK=false should not pass")
	}
}

func TestVerifyResult_Pass_WithError(t *testing.T) {
	r := VerifyResult{VMFound: true, VMRunning: true, QGAOK: true, SendKeyOK: true, Error: "oops"}
	if r.Pass() {
		t.Error("result with non-empty Error should not pass")
	}
}

func TestVerifyResult_Pass_Empty(t *testing.T) {
	if (VerifyResult{}).Pass() {
		t.Error("zero-value result should not pass")
	}
}
