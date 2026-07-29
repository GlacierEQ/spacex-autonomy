// Package autonomy implements a high-throughput event-driven flight state machine
// for autonomous abort decision-making with sub-100μs state transitions.
package autonomy

import (
	"fmt"
	"math"
	"sync"
	"time"
)

// FlightPhase represents the current phase of the launch vehicle
type FlightPhase int

const (
	PhasePrelaunch FlightPhase = iota
	PhaseIgnition
	PhaseLiftoff
	PhaseMaxQ
	PhaseMECO       // Main Engine Cutoff
	PhaseStagesSep
	PhaseSES1       // Second Engine Start
	PhaseSECO       // Second Engine Cutoff
	PhaseCoast
	PhaseReentry
	PhaseLanding
	PhaseAbort
	PhaseSafed
)

func (p FlightPhase) String() string {
	names := []string{"PRELAUNCH", "IGNITION", "LIFTOFF", "MAX_Q", "MECO",
		"STAGE_SEP", "SES1", "SECO", "COAST", "REENTRY", "LANDING", "ABORT", "SAFED"}
	if int(p) < len(names) {
		return names[p]
	}
	return "UNKNOWN"
}

// SensorReading represents a single sensor measurement
type SensorReading struct {
	SensorID  string
	Value     float64
	Unit      string
	Timestamp time.Time
	Quality   float64 // 0.0 = bad, 1.0 = perfect
}

// AbortCriteria defines thresholds for autonomous abort
type AbortCriteria struct {
	MaxDynamicPressurePa float64 // Max-Q abort threshold
	MinThrustRatioN      float64 // Minimum thrust-to-weight ratio
	MaxDeviationDeg      float64 // Max trajectory deviation
	MaxRotationRateRads  float64 // Max angular velocity
	MinPropellantKg      float64 // Minimum propellant reserve
}

// DefaultAbortCriteria returns conservative abort thresholds
func DefaultAbortCriteria() AbortCriteria {
	return AbortCriteria{
		MaxDynamicPressurePa: 35000.0,  // ~35 kPa
		MinThrustRatioN:      1.1,       // 110% of gravity
		MaxDeviationDeg:      5.0,       // 5° corridor
		MaxRotationRateRads:  0.35,      // ~20°/s
		MinPropellantKg:      500.0,     // 500kg reserve
	}
}

// FlightState holds the complete vehicle state vector
type FlightState struct {
	Phase            FlightPhase
	MissionElapsed   time.Duration
	AltitudeM        float64
	VelocityMs       float64
	DynamicPressurePa float64
	ThrustN          float64
	MassKg           float64
	DeviationDeg     float64
	RotationRateRads float64
	PropellantKg     float64
	AbortScore       float64 // 0.0 = nominal, 1.0 = abort
}

// FlightFSM is the core autonomous flight state machine
type FlightFSM struct {
	mu       sync.RWMutex
	state    FlightState
	criteria AbortCriteria
	events   chan SensorReading
	history  []FlightState
	abortLog []string
}

// NewFlightFSM creates a new flight state machine
func NewFlightFSM(criteria AbortCriteria) *FlightFSM {
	return &FlightFSM{
		state: FlightState{
			Phase:  PhasePrelaunch,
			MassKg: 549054.0, // Falcon 9 wet mass
		},
		criteria: criteria,
		events:   make(chan SensorReading, 10000),
		history:  make([]FlightState, 0, 10000),
	}
}

// EvaluateAbort computes the abort score based on current state
func (fsm *FlightFSM) EvaluateAbort() float64 {
	s := fsm.state
	score := 0.0

	// Dynamic pressure check
	if s.DynamicPressurePa > fsm.criteria.MaxDynamicPressurePa {
		score += 0.4
	} else if s.DynamicPressurePa > fsm.criteria.MaxDynamicPressurePa*0.9 {
		score += 0.1 // Warning zone
	}

	// Thrust ratio check
	gravity := 9.80665
	thrustRatio := s.ThrustN / (s.MassKg * gravity)
	if thrustRatio < fsm.criteria.MinThrustRatioN && s.Phase > PhaseLiftoff {
		score += 0.3
	}

	// Trajectory deviation
	if s.DeviationDeg > fsm.criteria.MaxDeviationDeg {
		score += 0.2
	}

	// Rotation rate
	if s.RotationRateRads > fsm.criteria.MaxRotationRateRads {
		score += 0.15
	}

	// Propellant reserve
	if s.PropellantKg < fsm.criteria.MinPropellantKg && s.Phase < PhaseSECO {
		score += 0.1
	}

	return math.Min(score, 1.0)
}

// Transition attempts a phase transition and returns whether it was valid
func (fsm *FlightFSM) Transition(newPhase FlightPhase) bool {
	fsm.mu.Lock()
	defer fsm.mu.Unlock()

	// Validate transition (only forward, except abort)
	if newPhase != PhaseAbort && newPhase <= fsm.state.Phase {
		return false
	}

	fsm.state.Phase = newPhase
	fsm.history = append(fsm.history, fsm.state)
	return true
}

// ProcessSensor updates state from a sensor reading and evaluates abort
func (fsm *FlightFSM) ProcessSensor(reading SensorReading) {
	fsm.mu.Lock()
	defer fsm.mu.Unlock()

	switch reading.SensorID {
	case "dynamic_pressure":
		fsm.state.DynamicPressurePa = reading.Value
	case "thrust":
		fsm.state.ThrustN = reading.Value
	case "altitude":
		fsm.state.AltitudeM = reading.Value
	case "velocity":
		fsm.state.VelocityMs = reading.Value
	case "deviation":
		fsm.state.DeviationDeg = reading.Value
	case "rotation_rate":
		fsm.state.RotationRateRads = reading.Value
	case "propellant":
		fsm.state.PropellantKg = reading.Value
	}

	fsm.state.AbortScore = fsm.EvaluateAbort()

	if fsm.state.AbortScore >= 0.7 && fsm.state.Phase != PhaseAbort {
		fsm.state.Phase = PhaseAbort
		fsm.abortLog = append(fsm.abortLog, fmt.Sprintf(
			"ABORT triggered at T+%s: score=%.2f phase=%s alt=%.0fm",
			fsm.state.MissionElapsed, fsm.state.AbortScore,
			fsm.state.Phase.String(), fsm.state.AltitudeM))
	}
}

// State returns a copy of the current flight state (thread-safe)
func (fsm *FlightFSM) State() FlightState {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return fsm.state
}

// Stats returns FSM statistics
func (fsm *FlightFSM) Stats() map[string]interface{} {
	fsm.mu.RLock()
	defer fsm.mu.RUnlock()
	return map[string]interface{}{
		"phase":             fsm.state.Phase.String(),
		"abort_score":       fsm.state.AbortScore,
		"altitude_m":        fsm.state.AltitudeM,
		"velocity_ms":       fsm.state.VelocityMs,
		"dynamic_pressure":  fsm.state.DynamicPressurePa,
		"state_transitions": len(fsm.history),
		"abort_events":      len(fsm.abortLog),
	}
}
