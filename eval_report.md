# Vault Evaluation Report

**Generated:** 2026-11-10 17:32:29 UTC
**Total Queries:** 6
**Successful:** 6
**Errors:** 0
**Avg Latency:** 25950ms
**Avg Relevance:** 90.00%

---

## Summary by Role

| Role | Queries | Successful | Refused | Avg Relevance | Avg Latency |
|------|---------|------------|---------|---------------|-------------|
| admin | 3 | 3 | 0 | 86.67% | 27600ms |
| intern | 3 | 3 | 1 | 93.33% | 24300ms |

---

## Summary by Category

| Category | Queries | Successful | Avg Relevance |
|----------|---------|------------|---------------|
| Easy Lookup | 2 | 2 | 100.00% |
| Cross Doc Synthesis | 2 | 2 | 70.00% |
| Edge Case | 2 | 2 | 100.00% |

---

## Per-Question Details

### EL-001: What is the cloud native tools strategy?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 49547ms |
| Relevance | 100.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:32:24.504026+00:00 |

**Answer:**
```
The cloud native tools strategy at GitLab is a multifaceted approach aimed at modernizing application development and operations by leveraging cloud computing, containers, microservices, and Kubernetes. Here’s a comprehensive overview based on the provided sources:

1. **Cloud Native Definition and Adoption**:  
   Cloud native is an approach to application development and operation that relies on on-demand cloud resources, containers, and microservices to deliver high service levels while adapt...
```

**Citations:**
1. `doc_engineering_0009` — Technology Roadmap (score: 0.9858)
2. `doc_general_0098` — Product Principles (score: 0.4375)
3. `doc_engineering_0916` — Segmenting Self-Managed for a Cloud Native Future (score: 0.4760)
4. `doc_sales_0359` — Cloud Native Ecosystem Sales Enablement (score: 0.1170)
5. `doc_sales_0306` — Developer Advocacy: Mentoring and Coaching (score: 0.3953)

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 34408ms |
| Relevance | 100.00% |
| Citations | 6 |
| Timestamp | 2026-11-10T17:32:20.303430+00:00 |

**Answer:**
```
The cloud-native tools strategy at GitLab is centered around a **cloud-native first** approach, prioritizing development for cloud-native environments like Kubernetes clusters before supporting other platforms [doc_general_0098]. This strategy aligns with broader industry trends, including **multicloud adoption**, **Kubernetes**, **microservices**, **observability**, **progressive delivery**, and the migration of workloads to the cloud [doc_general_0080].  

Key objectives include enabling **end...
```

**Citations:**
1. `doc_general_0098` — Product Principles (score: 0.4382)
2. `doc_general_0080` — Biggest Tailwinds (score: 0.0792)
3. `doc_general_0632` — DevOps Platform POV Scope and Acceptance (score: 0.1513)
4. `doc_general_1388` — Cloud Native Tools Strategy Working Group (score: 0.0092)
5. `doc_general_0195` — Research Operations (ReOps) at GitLab (score: 0.0083)
... and 1 more

---

### CS-001: What security frameworks and standards does GitLab follow?

**Category:** Cross Doc Synthesis

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 22317ms |
| Relevance | 60.00% |
| Citations | 6 |
| Timestamp | 2026-11-10T17:31:57.275948+00:00 |

**Answer:**
```
GitLab adheres to several security frameworks and standards to ensure accountability, fairness, and transparency in its operations and communications with stakeholders. Here are the key frameworks and standards outlined in the provided sources:

1. **Governance, Risk, and Compliance (GRC) Framework**  
   GitLab’s security governance discipline follows the GRC framework to define, train, and measure security strategies and progress toward security objectives. This ensures accountability, fairnes...
```

**Citations:**
1. `doc_it_security_0120` — Security Governance Program (score: 0.9947)
2. `doc_it_security_0064` — Change Management Policy (score: 0.9931)
3. `doc_hr_0002` — GitLab Internal Acceptable Use Policy (score: 0.9921)
4. `doc_it_security_0050` — GitLab Security Logging Standards (score: 0.9835)
5. `doc_it_security_0044` — GitLab Cryptography Standard (score: 0.9805)
... and 1 more

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 32661ms |
| Relevance | 80.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:32:29.937703+00:00 |

**Answer:**
```
GitLab adheres to several security frameworks and standards to ensure robust data protection and compliance. Here’s a comprehensive overview based on the provided sources:

1. **SAFE Framework**: GitLab Legal has developed the SAFE framework to guide team members on determining which information is internal and which can be shared publicly. This framework helps comply with Regulation Fair Disclosure [doc_general_0694]. The Data Team and Support Engineers also follow the SAFE framework to handle ...
```

**Citations:**
1. `doc_general_0694` — Product Manager SAFE Guidance (score: 0.9911)
2. `doc_general_1370` — Infrastructure Standards (score: 0.9899)
3. `doc_general_0660` — GitLab Model Vendor Selection Guidelines (score: 0.9780)
4. `doc_general_0778` — Recruitment Privacy Policy (score: 0.9404)
5. `doc_general_0357` — Handling data as a Support Engineer (score: 0.8199)

---

### EC-001: What is the stock price of Apple?

**Category:** Edge Case

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 10935ms |
| Relevance | 100.00% |
| Citations | 1 |
| Timestamp | 2026-11-10T17:31:45.894955+00:00 |

**Answer:**
```
The sources do not provide a current stock price for Apple. However, they do offer some relevant financial information:

* **[doc_finance_0075]** Apple's 10-K filing for 2025 mentions the average price paid per share during specific repurchase periods in 2025, with the highest average being $210.43 (June 29, 2025 to August 2, 2025). This is not the current stock price but indicates a historical trading range.

* **[doc_finance_0075]**  Also states that Apple's common stock is traded on The Nasda...
```

**Citations:**
1. `doc_finance_0075` — Apple 10-K (2025-09-27) (score: 0.5137)

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 5831ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:32:26.134356+00:00 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

*Report generated by Vault Evaluation Framework*
