from dataclasses import dataclass


@dataclass
class FactorResult:
    codigo: str
    nombre: str
    cumple: bool
    valor: str


class ChairLawEvaluator:
    FACTORES = [
        ("tiempo_pie_continuo", "Tiempo de pie continuo"),
        ("cambio_postura", "Cambio de postura"),
        ("espacio_moverse", "Espacio para moverse"),
        ("malestares_reportados", "Malestares reportados"),
        ("superficie_tapete", "Superficie / tapete"),
        ("pausas_tareas_alterna", "Pausas y tareas alternas"),
        ("calzado", "Calzado"),
    ]

    def evaluate(self, context: dict) -> dict:
        factores = []
        for codigo, nombre in self.FACTORES:
            factores.append(
                {
                    "codigo": codigo,
                    "nombre": nombre,
                    "cumple": True,
                    "valor": "ok",
                }
            )

        tiempo_pie = context.get("tiempo_pie_continuo_horas", 0)
        alerta_bipedestacion_3h = tiempo_pie > 3.0
        cumple_ley_silla = not alerta_bipedestacion_3h

        return {
            "cumple_ley_silla": cumple_ley_silla,
            "alerta_bipedestacion_3h": alerta_bipedestacion_3h,
            "factores": factores,
        }
