// Package autonomy implements a deterministic flight-phase simulation state machine.
//
// It is a portfolio simulation component, not flight-certified software.
package autonomy

import (
	"errors"
	"fmt"
	"math"
	"sync"
	"time"
)

// Phase is a simulated mission phase.
type Phase uint8

const (
	Prelaunch Phase = iota
	Ignition
	Liftoff
	MaxQ
	MainEngineCutoff
	StageSeparation
	Coast
	Reentry
	Landing
	Abort
	Safed
)

var phaseNames = [...]string{
	"PRELAUNCH",
	"IGNITION",
	"LIFTOFF",
	"MAX_Q",
	"MECO",
	"STAGE_SEPARATION",
	"COAST",
	"REENTRY",
	"LANDING",
	"ABORT",
	"SAFED",
}

// String returns a stable machine-readable phase name.
func (p Phase) String() string {
	if int(p) >= len(phaseNames) {
		return "UNKNOWN"
	}
	return phaseNames[p]
}

// Criteria defines deterministic simulation thresholds.
type Criteria struct {
	MaxDynamicPressurePa float64
	MinThrustToWeight    float64
	MaxDeviationDeg      float64
	MaxRotationRateRads  float64
	MinPropellantKg      float64
	AbortThreshold       float64
}

// DefaultCriteria returns conservative demonstration thresholds.
func DefaultCriteria() Criteria {
	return Criteria{
		MaxDynamicPressurePa: 35_000,
		MinThrustToWeight:    1.1,
		MaxDeviationDeg:      5,
		MaxRotationRateRads:  0.35,
		MinPropellantKg:      500,
		AbortThreshold:       0.7,
	}
}

// Validate rejects non-finite or contradictory threshold sets.
func (c Criteria) Validate() error {
	values := []float64{
		c.MaxDynamicPressurePa,
		c.MinThrustToWeight,
		c.MaxDeviationDeg,
		c.MaxRotationRateRads,
		c.MinPropellantKg,
		c.AbortThreshold,
	}
	for _, value := range values {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return errors.New("criteria values must be finite")
		}
	}
	if c.MaxDynamicPressurePa <= 0 || c.MinThrustToWeight <= 0 || c.MaxDeviationDeg <= 0 || c.MaxRotationRateRads <= 0 || c.MinPropellantKg < 0 {
		return errors.New("criteria thresholds must be positive")
	}
	if c.AbortThreshold <= 0 || c.AbortThreshold > 1 {
		return errors.New("abort threshold must be within (0, 1]")
	}
	return nil
}

// State is the simulated vehicle state used by the threshold engine.
type State struct {
	Phase              Phase
	MissionElapsed     time.Duration
	AltitudeM          float64
	VelocityMPS        float64
	DynamicPressurePa  float64
	ThrustN            float64
	MassKg             float64
	DeviationDeg       float64
	RotationRateRads   float64
	PropellantKg       float64
	AbortScore         float64
	ProcessedReadings  uint64
	RejectedReadings   uint64
}

// Reading is one validated state update.
type Reading struct {
	SensorID string
	Value    float64
	Quality  float64
}

// FSM is a concurrency-safe deterministic simulation state machine.
type FSM struct {
	mu       sync.RWMutex
	state    State
	criteria Criteria
	history  []State
	abortLog []string
}

// New creates a simulation FSM.
func New(criteria Criteria, initialMassKg float64) (*FSM, error) {
	if err := criteria.Validate(); err != nil {
		return nil, err
	}
	if math.IsNaN(initialMassKg) || math.IsInf(initialMassKg, 0) || initialMassKg <= 0 {
		return nil, errors.New("initial mass must be finite and positive")
	}
	return &FSM{
		state: State{
			Phase:  Prelaunch,
			MassKg: initialMassKg,
		},
		criteria: criteria,
		history:  make([]State, 0, 32),
	}, nil
}

func scoreState(state State, criteria Criteria) float64 {
	score := 0.0
	if state.DynamicPressurePa > criteria.MaxDynamicPressurePa {
		score += 0.4
	} else if state.DynamicPressurePa > criteria.MaxDynamicPressurePa*0.9 {
		score += 0.1
	}

	if state.Phase >= Liftoff && state.MassKg > 0 {
		thrustToWeight := state.ThrustN / (state.MassKg * 9.80665)
		if thrustToWeight < criteria.MinThrustToWeight {
			score += 0.3
		}
	}
	if math.Abs(state.DeviationDeg) > criteria.MaxDeviationDeg {
		score += 0.2
	}
	if math.Abs(state.RotationRateRads) > criteria.MaxRotationRateRads {
		score += 0.15
	}
	if state.Phase < Coast && state.PropellantKg < criteria.MinPropellantKg {
		score += 0.1
	}
	return math.Min(score, 1)
}

// EvaluateAbort returns the current threshold score without mutating the FSM.
func (fsm *FSM) EvaluateAbort() float64 {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return scoreState(fsm.state, fsm.criteria)
}

var nextPhase = map[Phase]Phase{
	Prelaunch:        Ignition,
	Ignition:         Liftoff,
	Liftoff:          MaxQ,
	MaxQ:             MainEngineCutoff,
	MainEngineCutoff: StageSeparation,
	StageSeparation:  Coast,
	Coast:            Reentry,
	Reentry:          Landing,
	Landing:          Safed,
	Abort:            Safed,
}

// Transition advances one legal phase, or enters Abort from any non-safed phase.
func (fsm *FSM) Transition(newPhase Phase) bool {
	fsm.mu.Lock()
	defer fsm.mu.Unlock()

	if fsm.state.Phase == Safed {
		return false
	}
	if newPhase != Abort && nextPhase[fsm.state.Phase] != newPhase {
		return false
	}
	fsm.state.Phase = newPhase
	fsm.history = append(fsm.history, fsm.state)
	return true
}

// Process applies one validated reading and returns the resulting state snapshot.
func (fsm *FSM) Process(reading Reading) (State, error) {
	if reading.SensorID == "" {
		return State{}, errors.New("sensor ID must be non-empty")
	}
	if math.IsNaN(reading.Value) || math.IsInf(reading.Value, 0) {
		return State{}, errors.New("sensor value must be finite")
	}
	if math.IsNaN(reading.Quality) || math.IsInf(reading.Quality, 0) || reading.Quality < 0 || reading.Quality > 1 {
		return State{}, errors.New("sensor quality must be within [0, 1]")
	}

	fsm.mu.Lock()
	defer fsm.mu.Unlock()

	if reading.Quality < 0.2 {
		fsm.state.RejectedReadings++
		return fsm.state, nil
	}

	switch reading.SensorID {
	case "dynamic_pressure":
		fsm.state.DynamicPressurePa = reading.Value
	case "thrust":
		fsm.state.ThrustN = reading.Value
	case "altitude":
		fsm.state.AltitudeM = reading.Value
	case "velocity":
		fsm.state.VelocityMPS = reading.Value
	case "deviation":
		fsm.state.DeviationDeg = reading.Value
	case "rotation_rate":
		fsm.state.RotationRateRads = reading.Value
	case "propellant":
		fsm.state.PropellantKg = reading.Value
	default:
		return State{}, fmt.Errorf("unknown sensor ID: %s", reading.SensorID)
	}

	fsm.state.ProcessedReadings++
	fsm.state.AbortScore = scoreState(fsm.state, fsm.criteria)
	if fsm.state.AbortScore >= fsm.criteria.AbortThreshold && fsm.state.Phase != Abort && fsm.state.Phase != Safed {
		fsm.state.Phase = Abort
		fsm.abortLog = append(fsm.abortLog, fmt.Sprintf("abort score %.2f", fsm.state.AbortScore))
		fsm.history = append(fsm.history, fsm.state)
	}
	return fsm.state, nil
}

// State returns a copy of the current state.
func (fsm *FSM) State() State {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.state
}

// Stats returns deterministic counters and the current phase.
func (fsm *FSM) Stats() map[string]any {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return map[string]any{
		"phase":              fsm.state.Phase.String(),
		"abort_score":        fsm.state.AbortScore,
		"state_transitions":  len(fsm.history),
		"abort_events":       len(fsm.abortLog),
		"processed_readings": fsm.state.ProcessedReadings,
		"rejected_readings":  fsm.state.RejectedReadings,
	}
}
