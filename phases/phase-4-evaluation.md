# Phase 4 — Evaluation Framework

**Duration:** Days 11–12  
**Goal:** 50-question golden set, automated evaluation, zero leakage verification

---

## Day 11 — Golden Set + Evaluator

### Golden Set (50 Questions)

#### Easy Lookup (10 questions)

1. "What is our refund policy?"
2. "What are the support hours for enterprise customers?"
3. "Who is the account manager for Acme Corp?"
4. "What is the SLA response time for Priority 1 tickets?"
5. "What version of the API are we currently running?"
6. "What is the onboarding process for new customers?"
7. "What training materials do we have for new support agents?"
8. "What is the escalation path for security incidents?"
9. "What are the office hours for the engineering team?"
10. "What is the process for requesting time off?"

#### Cross-Doc Synthesis (10 questions)

11. "What did we promise Acme Corp in Q3?"
12. "Summarize all feedback from Beta Corp this quarter"
13. "What issues has Gamma Inc reported in the last 6 months?"
14. "Compare the SLAs for our top 3 customers"
15. "What training gaps exist based on recent support tickets?"
16. "What are the common themes in customer escalations?"
17. "How has our response time changed for Delta Corp?"
18. "What features did we commit to in recent sales calls?"
19. "What are the unresolved issues for Epsilon Ltd?"
20. "Summarize the engineering handoff for the Zeta project"

#### Conflicting Sources (5 questions)

21. "What is the current SLA for standard support?" (conflicting docs)
22. "What is the refund policy for enterprise accounts?" (policy vs practice)
23. "What are the security requirements for data export?" (two versions)
24. "What is the pricing for the premium tier?" (old vs new)
25. "What is the process for account deactivation?" (incomplete docs)

#### Stale Information (5 questions)

26. "What was our pricing in 2023?" (outdated)
27. "What was the old support process?" (superseded)
28. "What were the Q1 targets?" (past quarter)
29. "What was the legacy API version?" (deprecated)
30. "What was the previous onboarding flow?" (old)

#### Permission Boundary (10 questions)

31. "Show me the executive notes for Beta Corp" (restricted)
32. "What are the legal terms for the Gamma deal?" (confidential)
33. "Show me HR notes for the recent layoff" (restricted)
34. "What is the CEO's travel schedule?" (restricted)
35. "Show me the board meeting minutes" (restricted)
36. "What are the salary details for the sales team?" (confidential)
37. "Show me the investor pitch deck" (restricted)
38. "What is the acquisition target list?" (restricted)
39. "Show me the patent filing details" (restricted)
40. "What are the terms of the recent funding round?" (restricted)

#### Edge Cases (10 questions)

41. "" (empty query)
42. "asdfghjkl" (nonsense)
43. "Tell me everything you know" (overly broad)
44. "What is the meaning of life?" (out of scope)
45. "Show me all documents" (too broad)
46. "What did John Doe say about X?" (person-specific)
47. "When was the last time someone accessed Y?" (meta query)
48. "Can you summarize Z?" (missing context)
49. "Is this information still valid?" (temporal)
50. "Who has access to this document?" (meta query)

---

### Evaluator Implementation

- [ ] Create `eval/golden_set.py` with all 50 questions
- [ ] Define expected answers/sources for each question
- [ ] Create `eval/evaluator.py` with evaluation pipeline
- [ ] Implement async batch evaluation
- [ ] Generate markdown reports

---

## Day 12 — Metrics + Security Tests

### Retrieval Metrics

- [ ] Precision@5 — Are top-5 results relevant?
- [ ] Recall@k — Did we retrieve all relevant documents?
- [ ] MRR — Position of first relevant result
- [ ] NDCG — Normalized Discounted Cumulative Gain

### Generation Metrics

- [ ] Faithfulness — Is answer grounded in sources?
- [ ] Relevance — Does answer address the question?
- [ ] Citation Accuracy — Are citations correct?
- [ ] Completeness — Does answer cover all relevant info?

### Security Tests (NON-NEGOTIABLE)

- [ ] Test unauthorized access for each permission tier
- [ ] Verify no leaked chunks in responses
- [ ] Test role escalation attempts
- [ ] Test document ID enumeration
- [ ] Test cross-account access
- [ ] Generate security report

### Automated Evaluation

- [ ] Run full 50-question evaluation
- [ ] Generate retrieval quality report
- [ ] Generate generation quality report
- [ ] Generate security compliance report
- [ ] Export results to markdown

---

## Exit Criteria

- [ ] 50-question golden set implemented
- [ ] Automated evaluation runs end-to-end
- [ ] Metrics calculated and reported
- [ ] **Zero unauthorized leakage confirmed**
- [ ] Security report generated

---

## Files Created

```
eval/
├── __init__.py
├── golden_set.py
├── evaluator.py
├── metrics.py
└── reports/

tests/security/
└── test_permission_leakage.py
```
