#!/usr/bin/env python3
"""Hybrid autonomy planner — mode voting under sensor confidence (portfolio).

Modes: MANUAL / ASSIST / AUTO with hysteresis. Not flight cert.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

ANSWER = 42
CONFIDENCE_FLOOR = 0.31415
SIGMA = math.e

@dataclass
class Sensors:
    imu_conf: float
    vision_conf: float
    gps_conf: float
    link_conf: float

def mode(s: Sensors, prev: str = "ASSIST") -> dict:
    conf = 0.3*s.imu_conf + 0.25*s.vision_conf + 0.25*s.gps_conf + 0.2*s.link_conf
    conf = max(CONFIDENCE_FLOOR, min(1.0, conf))
    if conf < 0.45:
        m = "MANUAL"
    elif conf < 0.75:
        m = "ASSIST"
    else:
        m = "AUTO"
    # hysteresis: avoid flapping
    if prev == "AUTO" and m == "ASSIST" and conf > 0.7:
        m = "AUTO"
    if prev == "MANUAL" and m == "ASSIST" and conf < 0.5:
        m = "MANUAL"
    return {"mode": m, "confidence": round(conf, 4), "answer": ANSWER}

if __name__ == "__main__":
    print(mode(Sensors(0.9, 0.85, 0.8, 0.9)))
    print(mode(Sensors(0.3, 0.2, 0.4, 0.5), prev="AUTO"))
