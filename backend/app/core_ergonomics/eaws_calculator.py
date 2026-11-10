class EawsCalculator:
    def calculate(
        self,
        trunk_flexion_deg: float,
        torso_twist_deg: float,
        work_above_shoulder: bool,
        work_below_knee: bool,
        force_kg: float,
        frequency_actions_per_shift: int,
    ) -> dict:
        if trunk_flexion_deg < 20:
            posture = 1
        elif trunk_flexion_deg < 45:
            posture = 3
        else:
            posture = 6

        posture += 0 if torso_twist_deg < 20 else 2
        posture += 2 if work_above_shoulder else 0
        posture += 2 if work_below_knee else 0

        if force_kg < 5:
            force = 1
        elif force_kg < 10:
            force = 3
        else:
            force = 6

        if frequency_actions_per_shift < 100:
            frequency = 1
        elif frequency_actions_per_shift < 500:
            frequency = 3
        else:
            frequency = 6

        total = posture + force + frequency

        if total <= 5:
            risk = "Bajo"
        elif total <= 10:
            risk = "Medio"
        else:
            risk = "Alto"

        return {
            "posture_score": posture,
            "force_score": force,
            "frequency_score": frequency,
            "total_score": total,
            "risk_level": risk,
        }
