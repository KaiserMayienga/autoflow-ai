/** Workshop knowledge base (Phase 1: keyword retrieval; Phase 2 swaps this for Qdrant RAG). */
export type KbEntry = { id: string; title: string; keywords: string[]; risk: "low" | "med" | "high"; hours: number; skus: string[]; doc: string };

export const KB: KbEntry[] = [
  { id: "brakes", title: "Brake pad and rotor inspection", keywords: ["brake", "brakes", "braking", "squeal", "squeals", "pedal"], risk: "high", hours: 1.5, skus: ["BRK-PAD", "BRK-ROT"], doc: "Brake Service Manual 4.2" },
  { id: "oil", title: "Oil and filter service", keywords: ["oil", "oil change"], risk: "low", hours: 0.7, skus: ["OIL-5L", "OIL-FLT"], doc: "Routine Maintenance Guide" },
  { id: "battery", title: "12V battery test and replacement", keywords: ["battery", "starting", "wont start", "dead battery", "12v"], risk: "low", hours: 0.5, skus: ["BAT-12V"], doc: "Electrical Procedures 2.1" },
  { id: "charging", title: "Charging port and HV safety inspection", keywords: ["charge", "charging", "charge port", "high voltage"], risk: "high", hours: 1.2, skus: ["EV-SEAL"], doc: "EV Safety Procedures 1.0" },
  { id: "ac", title: "AC recharge and leak test", keywords: ["ac", "air conditioning", "not cold", "cooling"], risk: "low", hours: 1.2, skus: ["AC-REF"], doc: "HVAC Guide 3.3" },
  { id: "led", title: "LED headlight upgrade", keywords: ["led", "headlight", "headlights", "lights"], risk: "low", hours: 1, skus: ["LED-KIT"], doc: "Upgrade Guide: Lighting" },
  { id: "dashcam", title: "Dashcam installation", keywords: ["dashcam", "dash cam", "camera"], risk: "low", hours: 1, skus: ["DASHCAM"], doc: "Upgrade Guide: Electronics" },
  { id: "alignment", title: "Wheel alignment and tyre rotation", keywords: ["alignment", "tyre", "tyres", "tire", "tires", "vibration", "pulling"], risk: "low", hours: 1, skus: ["ALIGN-SHIM"], doc: "Chassis Manual 5.4" },
  { id: "obd", title: "OBD-II diagnostic scan", keywords: ["check engine", "engine light", "warning light", "diagnostic", "obd"], risk: "med", hours: 0.8, skus: [], doc: "Diagnostics Guide 6.1" },
  { id: "urgent", title: "Urgent safety inspection", keywords: ["smoke", "overheat", "overheating", "fuel leak", "burning", "steering", "airbag"], risk: "high", hours: 1.5, skus: [], doc: "Safety Procedures 0.1" },
];
