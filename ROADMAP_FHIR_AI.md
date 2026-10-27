# Estado real y hoja de ruta: FHIR e IA

## Estado real
**FHIR:** existe `interoperability/fhir/resources/fhir_adapter.py` heredado de v0.1. **No es una integración funcional.** No está conectado a ningún endpoint, no se adaptó al esquema v2 (su import está neutralizado con `TriageRequestSchema = object`), no se validó contra ningún validador FHIR y no tiene pruebas. Problemas conocidos: `birthDate: null` es JSON inválido; `effectiveDateTime` usa la hora actual; no mapea conciencia ni oxígeno; el Bundle no incluye el Patient; el código LOINC de SpO₂ está por verificar.
**IA/ML:** **no existe ningún modelo**, dato de entrenamiento, métrica ni código de inferencia. La interfaz muestra únicamente el puntaje NEWS2. No debe afirmarse ninguna capacidad de IA ni cifras de precisión.

## Hoja de ruta FHIR (propuesta, requiere decisiones del producto)
1. Definir casos de uso y el sistema externo concreto (HIS/HCE, versión FHIR, perfiles; para Colombia, revisar la normativa de interoperabilidad vigente).
2. Reescribir el adaptador sobre el esquema v2 con `fhir.resources` o equivalente; Patient + Observation (signos vitales, perfil Vital Signs) + Bundle; elegir códigos LOINC verificados.
3. Validar con el validador oficial de HL7 y casos sintéticos; añadir pruebas.
4. Endpoint de exportación de solo lectura, con roles y auditoría; luego importación, con idempotencia y conciliación de identificadores.
5. Seguridad: OAuth2/SMART on FHIR o mTLS, acuerdos de acceso, cifrado, registro de accesos.
6. Pruebas de integración en un entorno de pruebas del tercero.

## Hoja de ruta IA (propuesta; nada de esto está iniciado)
1. Definir la pregunta clínica, la población y el uso previsto, y si aplica regulación de software como dispositivo médico.
2. Gobernanza de datos: base legal, autorización, anonimización, comité de ética; **sin datos clínicos reales hasta tenerla**.
3. Diseño experimental: partición temporal/por paciente (evitar fuga), línea base NEWS2, métricas de discriminación y calibración, análisis de sesgo por subgrupos.
4. Entrenamiento reproducible separado de la inferencia; versionado de datos, código y modelo; ficha del modelo.
5. Validación externa y prospectiva en modo sombra; revisión clínica antes de mostrar nada al usuario.
6. Monitoreo de deriva y plan de retirada. La IA solo complementaría, nunca sustituiría, la evaluación profesional.
