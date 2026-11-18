# Evaluation Report: AI Legal Document Assistant

**Date:** 2026-10-22 16:50:14
**Model:** gemini-3.1-flash-lite | **Temperature:** 0.0 | **Seed:** 42
**Benchmark Size:** 15 evaluation questions | **Seeded Risks:** 7

---

## 1. Table 7: Retrieval and Generation Metrics

| Metric | B1: Ungrounded | B2: BM25 + LLM | P: Proposed RAG |
|---|---|---|---|
| P@7 | N/A | 0.2024 | 0.2619 |
| MRR | N/A | 0.8333 | 0.5278 |
| Top-1 similarity | N/A | N/A | 0.7953 |
| Faithfulness (%) | 48.46 | 55.56 | 57.56 |
| Citation accuracy (%) | N/A | 93.33 | 83.33 |
| Hallucination rate (%) | 0.0 | 0.0 | 6.67 |
| Abstention accuracy (%) | 0.0 | 33.33 | 33.33 |
| Median latency (s) | 8.915 | 3.291 | 6.818 |

### Table 7 Metric Calculation Formulas:
- **P@7 (Precision at 7):** `Relevant_Chunks_in_Top7 / 7`. Evaluated for queries with target clauses in the contract. N/A for B1 (no retrieval).
- **MRR (Mean Reciprocal Rank):** `1 / Rank_of_First_Relevant_Chunk`. N/A for B1 (no retrieval).
- **Top-1 similarity:** Mean cosine similarity of top retrieved chunk. N/A for B1 and B2 (BM25 does not produce cosine similarities).
- **Faithfulness (%):** Percentage of grounded contract citations vs ungrounded generic assertions in the response.
- **Citation accuracy (%):** Percentage of responses containing valid clause/source citations. N/A for B1 (no sources provided).
- **Hallucination rate (%):** Percentage of responses that assert unsubstantiated general conditions without grounding.
- **Abstention accuracy (%):** Accuracy of abstaining on missing clauses (Sample 3).
- **Median latency (s):** Median end-to-end API response time across 15 queries.

---

## 2. Table 8: Risk Detection Evaluation (Proposed System)

| Seeded issue type | Seeded | Detected | Precision | Recall |
|---|---|---|---|---|
| One-sided termination | 1 | 1 | 100.0% | 100.0% |
| Excessive working hours | 1 | 1 | 100.0% | 100.0% |
| Broad non-compete | 1 | 1 | 100.0% | 100.0% |
| Unilateral deductions | 1 | 1 | 50.0% | 100.0% |
| Missing standard clause | 3 | 3 | 75.0% | 100.0% |
| **Overall** | **7** | **7** | **77.8%** | **100.0%** |

### Table 8 Calculation Methodology:
- **TP (True Positives):** Number of seeded risk instances correctly detected and flagged in the respective contract.
- **FP (False Positives):** Instances where a risk was falsely flagged in a document where it was not present.
- **FN (False Negatives):** Seeded risk instances missed by the model.
- **Precision:** `TP / (TP + FP)`
- **Recall:** `TP / (TP + FN)`
- **Overall (Micro-average):**
  - `Micro-Precision = sum(TP) / (sum(TP) + sum(FP))`
  - `Micro-Recall = sum(TP) / (sum(TP) + sum(FN))`

---
## 3. Ground Truth Breakdown
- **Sample 1 (Service Agreement):** Balanced baseline contract (0 seeded risks).
- **Sample 2 (Employment Agreement):** 4 high-risk clauses (one-sided termination, excessive hours, broad non-compete, unilateral deductions).
- **Sample 3 (Rental Agreement):** 3 missing clauses (termination notice, deposit refund terms, dispute resolution).
- **Sample 4 (Complex NDA):** 0 risky clauses (used for summarization and clause boundary extraction).
- **Total Seeded Risks:** 7
