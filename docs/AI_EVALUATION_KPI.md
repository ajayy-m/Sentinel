# Sentinel AI Evaluation KPI Framework

## 1. Model Performance Targets (Phase 1)

### Anomaly Detection

| KPI | Target | Rationale |
|-----|--------|-----------|
| False Positive Rate (FPR) | < 5% | Operator fatigue; aim for 95+ precision |
| False Negative Rate (FNR) | < 10% | Miss critical issues; aim for 90+ recall |
| Detection Latency | < 30s | Alert user within 1 payload window |
| Drift Detection Accuracy | 90%+ | Catch real behavior changes, ignore noise |

### Root-Cause Reasoning

| KPI | Target |
|-----|--------|
| Top-1 Accuracy (correct root cause in rank 1) | 60%+ |
| Top-3 Accuracy (correct cause in top 3 suggestions) | 80%+ |
| Explanation latency | < 2s |

### Recommendations

| KPI | Target |
|-----|--------|
| Actionability (operator can act on rec) | 90%+ |
| Success rate (recommended action fixes issue) | 70%+ |
| Recommendation latency | < 5s |

---

## 2. Baseline Rule-Only Detector (for comparison)

Before adding ML, implement a deterministic baseline to compare against.

### Baseline Rules

```python
class BaselineDetector:
    def detect_cpu_anomaly(self, cpu_pct, history):
        # Simple: CPU > 95th percentile of recent window (7-day rolling)
        p95 = np.percentile(history[-168:], 95)  # 7 days of hourly samples
        return cpu_pct > p95 * 1.1
    
    def detect_memory_leak(self, memory_pct, history):
        # Trend: memory increasing > 5% per hour for 3+ hours
        recent = history[-3:]
        slopes = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        return all(s > 5 for s in slopes)
    
    def detect_process_spike(self, process_count, history):
        # Process count > 90th percentile + 20 processes
        p90 = np.percentile(history[-100:], 90)
        return process_count > p90 + 20
```

### Baseline Performance Metrics

Run baseline on 1-week of production data:
- FPR, FNR
- Detection latency
- Precision/recall

**Acceptance:** Baseline should achieve 80%+ precision, 70%+ recall.

---

## 3. AI Model Evaluation Procedure

### Data Preparation

1. **Collect Ground Truth**
   - 1-week of production logs with manual labels (normal/anomaly/drift)
   - Annotator: operator validates each flagged event
   - Inter-rater agreement: 90%+ (2+ annotators agree)

2. **Train/Validation/Test Split**
   - 60% training, 20% validation, 20% test
   - Stratified by node type and incident category

### Evaluation Runs

1. **Baseline vs Heuristic Detector**
   - Run on test set
   - Calculate FPR, FNR, latency, precision, recall
   - Record as reference

2. **LLM (Ollama) Reasoning**
   - Feed current metrics + history + baseline hints to LLM
   - Request top-3 root causes with confidence
   - Compare LLM suggestions to ground truth
   - Record top-1, top-3 accuracy, latency

3. **Statistical Anomaly Scorer (z-score rolling)**
   - Run rolling z-score on test data
   - Compare to ground truth anomalies
   - Record detection accuracy, false positive rate

### Acceptance Criteria

- **FPR < 5%:** No more than 5% of normal events flagged
- **Detection Latency < 30s:** Flag within 30s of issue onset
- **Top-1 Accuracy > 60%:** LLM correct root cause in first suggestion at least 60% of the time
- **Baseline comparison:** AI model must exceed baseline detector by 10%+ on precision OR recall

### Quarterly Re-Evaluation

- Run evaluation on new data quarterly
- Track metric drift (model performance degradation)
- Retrain or adjust thresholds if performance drops below targets

---

## 4. Metrics Storage and Dashboarding

Store evaluation results in SQLite:

```sql
CREATE TABLE ai_evaluations (
    id INTEGER PRIMARY KEY,
    eval_date TEXT NOT NULL,
    model_name TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    false_positive_rate REAL,
    false_negative_rate REAL,
    precision REAL,
    recall REAL,
    detection_latency_seconds REAL,
    top1_accuracy REAL,
    top3_accuracy REAL,
    notes TEXT
);
```

Example:

```json
{
  "eval_date": "2026-05-01",
  "model_name": "ollama-mistral:7b-instruct",
  "dataset_name": "prod-2026-04-25-to-2026-05-01",
  "false_positive_rate": 0.03,
  "false_negative_rate": 0.08,
  "precision": 0.97,
  "recall": 0.92,
  "detection_latency_seconds": 18,
  "top1_accuracy": 0.65,
  "top3_accuracy": 0.82,
  "notes": "Ollama running on GPU, 2-3s inference time. Meeting all targets."
}
```

---

## 5. Implementation Roadmap

**v1.0 (Now):**
- Baseline rule detector implemented
- Rolling z-score anomaly scorer
- Heuristic root-cause correlator

**v1.1 (Q3 2026):**
- Ollama LLM integration (optional, local only)
- Evaluation framework with ground-truth labeling
- Quarterly re-evaluation process

**v2.0 (Q4 2026):**
- Custom fine-tuned model on Sentinel dataset
- Advanced drift detection (Isolation Forest)
- Multi-model ensembles (vote on root cause)

