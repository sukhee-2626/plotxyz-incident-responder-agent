export type FieldType = "text" | "textarea" | "number" | "checkbox";

export interface AgentField {
  name: string;
  label: string;
  type: FieldType;
  rows?: number;
  placeholder?: string;
}

export interface AgentConfig {
  slug: string;
  title: string;
  tagline: string;
  purpose: string;
  accent: string;
  features: string[];
  limitations: string[];
  fields: AgentField[];
  sample: Record<string, string | number | boolean>;
  repo: string;
}

export const agent: AgentConfig = {
  "slug": "plotxyz-incident-responder-agent",
  "title": "Incident Responder",
  "tagline": "Triage incidents and act fast.",
  "purpose": "Classifies incident severity from a description, lists affected services, and returns immediate actions plus a response timeline.",
  "accent": "#fb923c",
  "features": [
    "Severity classification",
    "Immediate action checklist",
    "Response timeline"
  ],
  "limitations": [
    "Severity is inferred from keywords, not real impact.",
    "The agent does not page anyone or create tickets."
  ],
  "fields": [
    {
      "name": "description",
      "label": "Incident description",
      "type": "textarea",
      "rows": 8,
      "placeholder": ""
    },
    {
      "name": "affected_services",
      "label": "Affected services (comma-separated)",
      "type": "text",
      "rows": 4,
      "placeholder": ""
    },
    {
      "name": "user_reported",
      "label": "Reported by a user",
      "type": "checkbox",
      "rows": 4,
      "placeholder": ""
    }
  ],
  "sample": {
    "description": "The checkout API is returning 500 errors for all users. Orders cannot be placed. This started after the 2:00 PM deployment.",
    "affected_services": "checkout-api, payment-service",
    "user_reported": true
  },
  "repo": "https://github.com/sukhee-2626/plotxyz-incident-responder-agent"
};
