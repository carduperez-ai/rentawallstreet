
import os
from datetime import timedelta
from decimal import Decimal
from typing import List, Dict
from src.domain.stock_entities import TaxEvent

class LegalJustificationAgent:
    """
    Agente Jurídico Autónomo e Independiente.
    Realiza un dictamen técnico objetivo sobre la aplicación de la normativa fiscal.
    """
    
    RISK_LEVELS = {
        "LOW": "🟢 RIESGO BAJO: Doctrina de la DGT clara (V0990-22).",
        "MEDIUM": "🟡 RIESGO MEDIO: Activo con naturaleza híbrida (Stablecoins/Fiat-backed).",
        "HIGH": "🔴 RIESGO ALTO: Consideración probable de valor negociable (ETPs, Derivados)."
    }

    def __init__(self, output_path: str = "reports/dictamen_juridico_fiscal_2025.md"):
        self.output_path = output_path
        self.audit_findings = []

    def analyze_and_justify(self, crypto_events: List[TaxEvent], all_trades: List):
        """
        Dictamen independiente del flujo de cálculo.
        """
        self.audit_findings = []
        
        # Mapa de compras para detectar recompras +/- 60 días
        buys_map = {}
        for t in all_trades:
            if t.direction == 'buy':
                asset = t.asset.upper()
                if asset not in buys_map: buys_map[asset] = []
                buys_map[asset].append(t)

        for te in crypto_events:
            # Análisis objetivo de cada evento de pérdida
            if te.gain_loss_eur < 0:
                risk, observation = self._evaluate_risk(te)
                
                # Buscar recompras (ventana de 60 días)
                start = te.date - timedelta(days=60)
                end = te.date + timedelta(days=60)
                rebuys = [b for b in buys_map.get(te.asset.upper(), []) 
                          if start <= b.date <= end and b.date != te.acquisition_date]
                
                if rebuys:
                    self.audit_findings.append({
                        "event": te,
                        "risk": risk,
                        "observation": observation,
                        "rebuys_detected": len(rebuys)
                    })

        self._generate_forensic_report()

    def _evaluate_risk(self, event: TaxEvent) -> tuple:
        asset = event.asset.upper()
        
        # 1. Criptoactivos Puros (Doctrina consolidada)
        if asset in ['BTC', 'ETH', 'SHIB', 'SOL', 'ADA', 'DOT']:
            return "LOW", "Moneda virtual sin consideración de valor homogéneo según DGT V0990-22."
            
        # 2. Stablecoins (Potencial interpretación como divisa)
        if asset in ['USDT', 'USDC', 'DAI', 'BUSD', 'EURC']:
            return "MEDIUM", "Stablecoin. Aunque no es valor homogéneo, su naturaleza fiat-peg podría ser objeto de analogía con divisas por la AEAT."
            
        # 3. ETPs / Derivados (Riesgo alto de ser considerados valores)
        if any(x in asset for x in ['ETP', 'ETN', 'FUTURE', 'PERP', 'OPTION']):
            return "HIGH", "Instrumento derivado o cotizado. Alta probabilidad de ser clasificado como valor homogéneo (Art. 33.5 f LIRPF)."
            
        return "LOW", "Criptoactivo genérico. Aplicable criterio de no-homogeneidad."

    def _generate_forensic_report(self):
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write("# DICTAMEN TÉCNICO DE AUDITORÍA JURÍDICO-FISCAL\n")
            f.write(f"**Fecha del informe:** {timedelta(days=0)}\n")
            f.write("**Estado:** Independiente y Objetivo\n\n")
            
            f.write("## 1. RESUMEN EJECUTIVO\n")
            f.write("Este informe evalúa de forma autónoma la deducibilidad de las pérdidas patrimoniales generadas en activos digitales, "
                    "contrastándolas con la regla de recompra de valores homogéneos (Art. 33.5 f LIRPF).\n\n")
            
            f.write("## 2. DESGLOSE DE HALLAZGOS Y CALIFICACIÓN DE RIESGO\n")
            
            if not self.audit_findings:
                f.write("✅ **Análisis completado:** No se han detectado operaciones que requieran justificación especial o supongan un riesgo de colisión normativa.\n")
            else:
                for find in self.audit_findings:
                    te = find['event']
                    f.write(f"### Activo: {te.asset} | {self.RISK_LEVELS[find['risk']]}\n")
                    f.write(f"- **Operación:** Venta el {te.date.strftime('%d/%m/%Y')} con pérdida de {abs(te.gain_loss_eur):.2f} €\n")
                    f.write(f"- **Conflicto detectado:** Recompra en ventana de 60 días ({find['rebuys_detected']} ops).\n")
                    f.write(f"- **Dictamen del Agente:** {find['observation']}\n")
                    if find['risk'] == "HIGH":
                        f.write("> ⚠️ **ADVERTENCIA:** Se recomienda precaución en la deducibilidad de esta pérdida específica.\n")
                    f.write("\n")
            
            f.write("\n## 3. CONCLUSIÓN TÉCNICA\n")
            f.write("La aplicación de la base imponible del ahorro en este ejercicio se considera, con carácter general, alineada "
                    "con la doctrina vigente de la DGT. La no aplicación de la regla de los dos meses a las monedas virtuales "
                    "cumple con el principio de tipicidad tributaria.\n")
            
            f.write("\n---\n*Este dictamen ha sido generado por un agente autónomo y no constituye asesoramiento financiero, sino un análisis técnico de cumplimiento normativo.*")

        print(f"  [AGENT] Dictamen forense generado en: {self.output_path}")
