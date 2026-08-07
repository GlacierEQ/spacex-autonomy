package autonomy

import (
	"math"
	"sync"
	"testing"
)

func newTestFSM(t *testing.T) *FSM {
	t.Helper()
	fsm, err := New(DefaultCriteria(), 1_000)
	if err != nil {
		t.Fatalf("New returned error: %v", err)
	}
	return fsm
}

func TestNewRejectsInvalidCriteria(t *testing.T) {
	criteria := DefaultCriteria()
	criteria.AbortThreshold = 0
	if _, err := New(criteria, 1_000); err == nil {
		t.Fatal("expected invalid abort threshold to fail")
	}
	if _, err := New(DefaultCriteria(), math.NaN()); err == nil {
		t.Fatal("expected non-finite mass to fail")
	}
}

func TestTransitionRequiresNextLegalPhase(t *testing.T) {
	fsm := newTestFSM(t)
	if fsm.Transition(MaxQ) {
		t.Fatal("skipping mission phases must fail")
	}
	if !fsm.Transition(Ignition) || !fsm.Transition(Liftoff) {
		t.Fatal("legal adjacent transitions must pass")
	}
	if fsm.Transition(Ignition) {
		t.Fatal("backward transition must fail")
	}
}

func TestAbortMayOccurFromActivePhaseAndThenSafe(t *testing.T) {
	fsm := newTestFSM(t)
	if !fsm.Transition(Abort) {
		t.Fatal("abort transition should be allowed")
	}
	if !fsm.Transition(Safed) {
		t.Fatal("abort should transition to safed")
	}
	if fsm.Transition(Abort) {
		t.Fatal("safed phase must be terminal")
	}
}

func TestProcessRejectsMalformedOrUnknownReadings(t *testing.T) {
	fsm := newTestFSM(t)
	cases := []Reading{
		{SensorID: "", Value: 1, Quality: 1},
		{SensorID: "altitude", Value: math.Inf(1), Quality: 1},
		{SensorID: "altitude", Value: 1, Quality: 2},
		{SensorID: "unknown", Value: 1, Quality: 1},
	}
	for _, reading := range cases {
		if _, err := fsm.Process(reading); err == nil {
			t.Fatalf("expected reading %+v to fail", reading)
		}
	}
}

func TestLowQualityReadingIsCountedButNotApplied(t *testing.T) {
	fsm := newTestFSM(t)
	state, err := fsm.Process(Reading{SensorID: "altitude", Value: 500, Quality: 0.1})
	if err != nil {
		t.Fatalf("Process returned error: %v", err)
	}
	if state.AltitudeM != 0 || state.RejectedReadings != 1 || state.ProcessedReadings != 0 {
		t.Fatalf("unexpected low-quality state: %+v", state)
	}
}

func TestThresholdCombinationTriggersAbort(t *testing.T) {
	fsm := newTestFSM(t)
	if !fsm.Transition(Ignition) || !fsm.Transition(Liftoff) {
		t.Fatal("failed to enter liftoff")
	}
	readings := []Reading{
		{SensorID: "dynamic_pressure", Value: 40_000, Quality: 1},
		{SensorID: "thrust", Value: 0, Quality: 1},
	}
	var state State
	for _, reading := range readings {
		var err error
		state, err = fsm.Process(reading)
		if err != nil {
			t.Fatalf("Process returned error: %v", err)
		}
	}
	if state.Phase != Abort || state.AbortScore < DefaultCriteria().AbortThreshold {
		t.Fatalf("expected abort state, got %+v", state)
	}
}

func TestConcurrentReadsRemainRaceSafe(t *testing.T) {
	fsm := newTestFSM(t)
	var wait sync.WaitGroup
	for i := 0; i < 20; i++ {
		wait.Add(1)
		go func(value float64) {
			defer wait.Done()
			_, _ = fsm.Process(Reading{SensorID: "altitude", Value: value, Quality: 1})
			_ = fsm.State()
			_ = fsm.EvaluateAbort()
			_ = fsm.Stats()
		}(float64(i))
	}
	wait.Wait()
	if fsm.State().ProcessedReadings != 20 {
		t.Fatalf("expected 20 readings, got %d", fsm.State().ProcessedReadings)
	}
}
