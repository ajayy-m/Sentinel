# LLM Enhancements Guide

**Date:** 2026-05-05  
**Status:** All LLM modules implemented and integrated

---

## Overview

Comprehensive LLM enhancements have been added to Sentinel, providing intelligent contextual analysis, recommendations, and operator support. All modules degrade gracefully if Ollama is unavailable.

---

## Modules Implemented

### 1. Enhanced Root-Cause Analysis (`sentinel/ai/enhanced_root_cause.py`)

**Purpose:** Generate deeper root-cause hypotheses using LLM with historical context.

**Key Features:**
- Analyzes time-series metric trends
- Correlates multiple anomalies
- Provides multi-hypothesis analysis with confidence levels
- Identifies supporting evidence and next investigation steps

**Example Usage:**

```python
from sentinel.ai.enhanced_root_cause import EnhancedRootCauseAnalyzer

analyzer = EnhancedRootCauseAnalyzer.from_config(config)

analysis = analyzer.analyze_anomaly_pattern(
    node_id="node-1",
    anomalies=[{"metric": "cpu", "score": 85}],
    changes=[{"event_type": "process_spike"}],
    metrics_history={"cpu": [45, 48, 52, 65, 78]},
)

if analysis:
    print(f"Hypothesis: {analysis['hypothesis']}")
    print(f"Confidence: {analysis['confidence']}")
    print(f"Next Steps: {analysis['recommended_investigation']}")
```

**Config Settings:**
```yaml
root_cause:
  enable_llm: true
  window_seconds: 60
```

---

### 2. LLM-Based Recommendation Generation (`sentinel/ai/llm_recommendation.py`)

**Purpose:** Generate context-aware, actionable recommendations using LLM.

**Key Features:**
- Considers historical similar incidents
- Assigns priority and risk levels
- Generates specific, implementable actions
- Provides clear rationale for operator approval

**Example Usage:**

```python
from sentinel.ai.llm_recommendation import LLMRecommendationGenerator

gen = LLMRecommendationGenerator.from_config(config)

rec = gen.generate_contextual_recommendation(
    node_id="node-1",
    alerts=[{"severity": "critical", "category": "cpu", "message": "CPU at 95%"}],
    root_cause_hints=[{"message": "Process memory leak causing CPU thrashing"}],
    historical_context={"similar_count": 3, "last_resolution": "restart process"},
)

if rec:
    print(f"Action: {rec['title']}")
    print(f"Steps: {rec['suggested_actions']}")
    print(f"Risk: {rec['risk_level']}")
```

**Config Settings:**
```yaml
recommendations:
  llm_enabled: true
  cooldown_seconds: 30
```

---

### 3. Natural Language Alert Summarization (`sentinel/ai/alert_summarizer.py`)

**Purpose:** Generate human-friendly summaries of alert clusters.

**Key Features:**
- Converts multiple technical alerts into clear headlines
- Provides business-friendly explanations
- Identifies affected systems
- Estimates severity for quick triage

**Example Usage:**

```python
from sentinel.ai.alert_summarizer import AlertSummarizer

summarizer = AlertSummarizer.from_config(config)

summary = summarizer.summarize_alert_cluster(
    node_id="node-1",
    alerts=[
        {"severity": "critical", "category": "cpu", "message": "CPU > 95%"},
        {"severity": "warning", "category": "memory", "message": "Memory pressure high"},
    ],
    root_cause_hints=[{"message": "Memory leak in service X"}],
)

if summary:
    print(f"Headline: {summary['headline']}")
    print(f"Explanation: {summary['explanation']}")
    print(f"Affected: {summary['affected_systems']}")
```

**Config Settings:**
```yaml
alerts:
  nlp_summaries: true
```

---

### 4. Risk Assessment & Decision Support (`sentinel/ai/risk_assessment.py`)

**Purpose:** Assess risk of proposed actions and provide decision support.

**Key Features:**
- Identifies risk factors
- Suggests mitigations
- Estimates blast radius and recovery time
- Provides approval recommendations (yes/proceed_with_caution/no)

**Example Usage:**

```python
from sentinel.ai.risk_assessment import RiskAssessmentEngine

engine = RiskAssessmentEngine.from_config(config)

assessment = engine.assess_action_risk(
    node_id="node-1",
    action_title="Restart memory-leaking service",
    action_description="Force restart service X to clear memory",
    affected_services=["api-server", "web-frontend"],
    current_state={"cpu": 90, "memory": 95, "active_connections": 5000},
)

if assessment:
    print(f"Risk Level: {assessment['risk_level']}")
    print(f"Recommendation: {assessment['approval_recommendation']}")
    print(f"Mitigations: {assessment['mitigations']}")
```

**Config Settings:**
```yaml
approval_gate:
  llm_risk_assessment: true
  request_cooldown_seconds: 30
```

---

### 5. Feedback Loop Learning (`sentinel/ai/feedback_learner.py`)

**Purpose:** Track operator decisions and learn patterns to improve future recommendations.

**Key Features:**
- Records all operator feedback (approve/reject/modify)
- Tracks outcomes of implemented recommendations
- Provides performance analytics by recommendation category
- Exports training data for future model tuning
- Identifies which recommendation types are most trusted

**Example Usage:**

```python
from sentinel.ai.feedback_learner import FeedbackLoopLearner

learner = FeedbackLoopLearner()

# Record operator feedback
learner.record_feedback(
    recommendation_id=123,
    recommendation={"category": "investigate", "priority": "high"},
    decision="approved",
    actor="ops-engineer-john",
    rationale="Clear root cause from history",
    actual_outcome="Service restarted successfully",
)

# Get summary statistics
summary = learner.get_feedback_summary()
print(f"Approval Rate: {summary['approval_rate_pct']}%")
print(f"LLM Approval Rate: {summary['llm_approval_rate_pct']}%")

# Get learning insights for tuning
insights = learner.get_learning_insights()
for cat, perf in insights["category_performance"].items():
    print(f"{cat}: {perf['approval_rate']}% approved → {perf['recommendation']}")

# Export training data
learner.export_training_data("./model_training_data.jsonl")
```

**Database:** Feedback stored in `./data/recommendation_feedback.jsonl`

---

## Integration Points

### In Collector (`sentinel/core/collector.py`)

```python
# Add to collector initialization
from sentinel.ai.enhanced_root_cause import EnhancedRootCauseAnalyzer
from sentinel.ai.alert_summarizer import AlertSummarizer
from sentinel.ai.feedback_learner import FeedbackLoopLearner

self.enhanced_rc = EnhancedRootCauseAnalyzer.from_config(config)
self.alert_summarizer = AlertSummarizer.from_config(config)
self.feedback_learner = FeedbackLoopLearner()

# When generating hints, use enhanced analyzer
hints = self.enhanced_rc.analyze_anomaly_pattern(...)

# When storing alerts, add summary
summary = self.alert_summarizer.summarize_alert_cluster(alerts)
```

### In Recommendations (`sentinel/core/recommendations.py`)

```python
from sentinel.ai.llm_recommendation import LLMRecommendationGenerator
from sentinel.ai.risk_assessment import RiskAssessmentEngine

self.llm_gen = LLMRecommendationGenerator.from_config(config)
self.risk_engine = RiskAssessmentEngine.from_config(config)

# Generate smarter recommendations
llm_rec = self.llm_gen.generate_contextual_recommendation(...)

# Assess risk of each recommendation
risk = self.risk_engine.assess_action_risk(...)
```

### In UI (`sentinel/ui/main_window.py`)

Display risk assessments and learning analytics:

```python
# Show risk assessment for each action queue item
risk = self._config.get("risk_assessment", {})
risk_label = QLabel(f"Risk: {risk['risk_level']} ({risk['confidence']})")
risk_label.setStyleSheet("color: red;" if risk['risk_level'] == "high" else "color: orange;")

# Show learning stats
from sentinel.ai.feedback_learner import FeedbackLoopLearner
learner = FeedbackLoopLearner()
summary = learner.get_feedback_summary()
stats_label = QLabel(f"Approval Rate: {summary['approval_rate_pct']}%")
```

---

## Configuration

Add these to `config/config.yaml`:

```yaml
ai:
  llm:
    base_url: "${OLLAMA_BASE_URL:http://localhost:11434}"
    model: "${OLLAMA_MODEL:mistral:7b-instruct}"
    timeout_seconds: 30

root_cause:
  enable_llm: true
  window_seconds: 60
  cooldown_seconds: 30
  min_repeated_anomalies: 2
  min_metric_instability_count: 3

recommendations:
  llm_enabled: true
  cooldown_seconds: 30

alerts:
  nlp_summaries: true

approval_gate:
  llm_risk_assessment: true
  request_cooldown_seconds: 30
```

---

## Ollama Setup

If Ollama is not running, the pilot stack now tries to start it automatically when you launch the app. If the Ollama CLI is unavailable, LLM features gracefully degrade to heuristic-only mode:

```bash
# Download & run Ollama locally
# From: https://ollama.ai

# Start Ollama server
ollama serve

# In another terminal, pull model (one-time)
ollama pull mistral:7b-instruct

# Verify running
curl http://localhost:11434/api/tags
```

Alternative models:

```bash
ollama pull llama2:13b        # More powerful, slower
ollama pull neural-chat       # Faster, lighter
ollama pull dolphin-mixtral   # Excellent reasoning
```

---

## Performance & Tuning

### LLM Response Times
- Root-cause analysis: ~2-5 seconds
- Recommendation generation: ~3-7 seconds
- Alert summarization: ~1-3 seconds
- Risk assessment: ~3-6 seconds

### Token Limits (to prevent runaway costs/delays)
- Root-cause max tokens: 300
- Recommendations max tokens: 400
- Alert summary max tokens: 250
- Risk assessment max tokens: 400

### Temperature Settings (tuning creativity vs consistency)
- Root-cause: 0.3 (deterministic, consistent analysis)
- Recommendations: 0.4 (some variety, mostly consistent)
- Alert summary: 0.3 (clear, factual)
- Risk assessment: 0.3 (conservative on risk)

---

## Monitoring & Analytics

### Check LLM Health

```python
from sentinel.ai.llm import OllamaClient

client = OllamaClient.from_config(config)
if client.is_healthy():
    models = client.list_models()
    print(f"LLM Ready: {models}")
else:
    print("LLM Unavailable - heuristic mode active")
```

### View Recommendation Performance

```python
from sentinel.ai.feedback_learner import FeedbackLoopLearner

learner = FeedbackLoopLearner()
insights = learner.get_learning_insights()

for category, perf in insights.get("category_performance", {}).items():
    print(f"{category}: {perf['approval_rate']}% approved")
    print(f"  Recommendation: {perf['recommendation']}")
```

### Export Training Data for Future Model Tuning

```python
learner.export_training_data("./recommendation_training_data.jsonl")
# Use this file to fine-tune custom LLM models
```

---

## Degradation & Fallback Behavior

| Component | If LLM Unavailable | Fallback |
|-----------|-------------------|----------|
| Enhanced root-cause | Uses heuristic-only analysis | Returns standard hints |
| LLM recommendations | Uses hardcoded rules | Returns basic recommendations |
| Alert summarization | Skipped | Shows raw alert list |
| Risk assessment | Skipped | Operator must assess manually |
| Feedback learning | Still records, no LLM tuning | Collects data for offline analysis |

All degradation is graceful - system continues operating without LLM.

---

## Testing LLM Modules

```python
# Test script: scripts/test_llm_modules.py
python scripts/test_llm_modules.py

# This will:
# 1. Test LLM connectivity
# 2. Run sample analysis on mock data
# 3. Generate test recommendations
# 4. Validate JSON responses
# 5. Check feedback recording
```

---

## Next Steps

1. **Pilot LLM features** on 2-3 nodes during the 1-week pilot
2. **Collect feedback** on recommendation quality
3. **Tune temperature/prompt** parameters based on results
4. **Fine-tune custom model** if approval rates drop below 50%
5. **Export training data** for future offline model training

---

See [PILOT_SIMULATION_TEST_PLAN.md](PILOT_SIMULATION_TEST_PLAN.md) for LLM feature testing during pilot.
