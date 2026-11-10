# Vault Evaluation Report

**Generated:** 2026-11-10 17:15:08 UTC
**Total Queries:** 60
**Successful:** 40
**Errors:** 20
**Avg Latency:** 21797ms
**Avg Relevance:** 65.17%

---

## Summary by Role

| Role | Queries | Successful | Refused | Avg Relevance | Avg Latency |
|------|---------|------------|---------|---------------|-------------|
| admin | 30 | 19 | 6 | 65.88% | 22389ms |
| intern | 30 | 21 | 8 | 64.52% | 21262ms |

---

## Summary by Category

| Category | Queries | Successful | Avg Relevance |
|----------|---------|------------|---------------|
| Easy Lookup | 30 | 21 | 62.70% |
| Cross Doc Synthesis | 10 | 6 | 48.33% |
| Permission Boundary | 10 | 3 | 0.00% |
| Edge Case | 10 | 10 | 100.00% |

---

## Per-Question Details

### EL-001: What is the cloud native tools strategy?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 23637ms |
| Relevance | 100.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:03:56.662449 |

**Answer:**
```
The cloud native tools strategy involves adopting an approach to application development and operation centered around cloud computing, leveraging technologies like containers and microservices to achieve high service levels and adaptability [doc_engineering_0009]. GitLab's strategy includes compartmentalizing state by removing shared local state from application components, particularly those using shared POSIX storage (NFS), and aligning stateful services like the main database (Postgres) with...
```

**Citations:**
1. `doc_engineering_0009` — Technology Roadmap (score: 0.9858)
2. `doc_engineering_0916` — Segmenting Self-Managed for a Cloud Native Future (score: 0.4758)
3. `doc_general_0098` — Product Principles (score: 0.4382)
4. `doc_sales_0306` — Developer Advocacy: Mentoring and Coaching (score: 0.3943)
5. `doc_sales_0359` — Cloud Native Ecosystem Sales Enablement (score: 0.1174)

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:10:28.558277 |

**Answer:**
```

```

---

### EL-002: How does the onboarding process work at GitLab?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 27934ms |
| Relevance | 25.00% |
| Citations | 4 |
| Timestamp | 2026-11-10T17:04:00.961648 |

**Answer:**
```
The onboarding process at GitLab is a structured, self-driven, and asynchronous experience designed to help new team members become productive within the first few weeks of their employment. Here’s how it works, synthesized from all provided sources:

1. **Overview and Purpose**:  
   Onboarding at GitLab refers to the initial weeks after hiring, managed cross-functionally by Corporate Security, People Operations, and Security Assurance [doc_it_security_0418]. It is self-driven and self-learning...
```

**Citations:**
1. `doc_it_security_0418` — CorpSec Onboarding Services (score: 0.9999)
2. `doc_general_1522` — The complete guide to remote onboarding for new-hires (score: 0.9999)
3. `doc_hr_0057` — GitLab Onboarding (score: 0.9999)
4. `doc_it_security_0229` — HackerOne Process (score: 0.9993)

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 41877ms |
| Relevance | 25.00% |
| Citations | 4 |
| Timestamp | 2026-11-10T17:10:13.597244 |

**Answer:**
```
The onboarding process at GitLab is designed to be **self-driven, self-learning, and asynchronous**, reflecting the company’s remote work culture and values [doc_general_1522]. It is structured around a standardized set of tasks and steps documented in an **onboarding issue template**, which new hires complete in a GitLab issue [doc_general_1522].  

**Key Components of Onboarding:**  
1. **Onboarding Issue Template**: Contains sequential tasks for the first 30 days, such as setting up accounts,...
```

**Citations:**
1. `doc_general_1522` — The complete guide to remote onboarding for new-hires (score: 0.9999)
2. `doc_general_1048` — Data Team Programs (score: 0.9983)
3. `doc_general_0922` — GitLab IT Onboarding 101 (score: 0.9978)
4. `doc_general_1344` — A Day in the Life of a CSE (score: 0.9978)

---

### EL-003: What are the working groups at GitLab?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 47594ms |
| Relevance | 66.67% |
| Citations | 3 |
| Timestamp | 2026-11-10T17:04:20.623200 |

**Answer:**
```
GitLab's working groups are cross-functional teams with defined roles and responsibilities, tasked with achieving high-impact business goals quickly. They disband once their goals are met, as defined by exit criteria, to avoid bureaucracy [doc_general_1475, doc_engineering_0352]. 

**Types of Working Groups:**

* **Stage Working Groups:** Focus on initiatives requiring collaboration between multiple groups within a specific stage. They are driven by stage-level product direction and can consist ...
```

**Citations:**
1. `doc_engineering_0352` — Plan (score: 0.9999)
2. `doc_general_1375` — GitLab Administration Working Group (score: 0.9987)
3. `doc_general_1410` — Feature Flag usage Working Group (score: 0.9973)

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:10:45.450125 |

**Answer:**
```

```

---

### EL-004: What is GitLab's remote work policy?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:04:56.669090 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 20993ms |
| Relevance | 50.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:10:34.590111 |

**Answer:**
```
GitLab operates as a fully remote company, empowering all team members to work from anywhere they feel most fulfilled, with no requirement for in-person meetings, even for executives [doc_general_1585]. This "all-remote" approach applies to all employees, including those at GitLab France S.A.S., who work remotely 100% of the time [doc_general_0763]. 

**Key aspects of GitLab's remote work policy include:**

* **Global Reach:** GitLab employs over 1,700 team members in more than 65 countries, lev...
```

**Citations:**
1. `doc_general_1585` — GitLab's Guide to All-Remote (score: 0.9922)
2. `doc_general_0763` — GitLab France S.A.S. Remote Work Charter (score: 0.9992)
3. `doc_general_1529` — Remote/work-from-home starter guide (score: 0.9953)
4. `doc_general_1641` — Business Continuity Plan (score: 0.9982)
5. `doc_general_0766` — GitLab India Private Limited Policy Against Sexual Harassment (score: 0.9997)

---

### EL-005: What are the code of conduct rules?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 26523ms |
| Relevance | 75.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:04:27.484700 |

**Answer:**
```
The Code of Conduct rules encompass several key areas, including community behavior, supplier responsibilities, and handling violations. Here’s a comprehensive overview based on the provided sources:

1. **Community Code of Conduct (GitLab):**  
   - Prohibits trolling, insulting/derogatory comments, and personal or political attacks [doc_sales_0432].  
   - Applies to the forum platform and wider GitLab Community [doc_sales_0435, doc_general_0280].  
   - Violations can be flagged for moderator...
```

**Citations:**
1. `doc_sales_0432` — Code of Conduct Enforcement (score: 0.7413)
2. `doc_sales_0435` — Forum workflow (score: 0.9777)
3. `doc_legal_0117` — ACCURAYINC 09 01 2010-EX-10.31-DISTRIBUTOR AGREEMENT (score: 0.8650)
4. `doc_it_security_0229` — HackerOne Process (score: 0.8933)
5. `doc_general_0280` — Support Engineer Resources (score: 0.8582)

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 56822ms |
| Relevance | 100.00% |
| Citations | 4 |
| Timestamp | 2026-11-10T17:11:25.380547 |

**Answer:**
```
GitLab's Code of Conduct encompasses several guidelines and policies that govern the behavior and interactions of team members, customers, and participants in GitLab events. Here are the key rules synthesized from the provided sources:

1. **Focus on the design work, not the designer** during critique sessions [doc_general_0203].  
2. **Communicate with respect** and avoid offensive language or behavior [doc_general_0203, doc_general_0280, doc_general_1362].  
3. **Challenge directly while showi...
```

**Citations:**
1. `doc_general_0203` — Product Designer Workflow (score: 0.9904)
2. `doc_general_1362` — GitLab Events Code of Conduct (score: 0.0294)
3. `doc_general_0097` — People Policies (score: 0.1194)
4. `doc_general_0064` — Entity-Specific Employment Policies (score: 0.1439)

---

### EL-006: What is the NIST Cybersecurity Framework?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 49257ms |
| Relevance | 100.00% |
| Citations | 3 |
| Timestamp | 2026-11-10T17:05:09.880546 |

**Answer:**
```
The NIST Cybersecurity Framework (CSF) is a set of guidelines and best practices for managing and reducing cybersecurity risks. It is developed by the National Institute of Standards and Technology (NIST) and is widely recognized as a standard for improving cybersecurity across various industries [doc_it_security_0134].  

The NIST CSF is referenced in multiple contexts:  
1. **Compliance and Industry Alignment**: GitLab’s proprietary security control framework (GCF) compares its controls agains...
```

**Citations:**
1. `doc_it_security_0134` — GitLab Security Compliance Controls (score: 0.1142)
2. `doc_sales_0384` — DevOps Solution Resource: Software Compliance (score: 0.8689)
3. `doc_it_security_0189` — Security Architecture (score: 0.5291)

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 5632ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:10:40.222724 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

### EL-007: What are the employee leave policies?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 34919ms |
| Relevance | 40.00% |
| Citations | 4 |
| Timestamp | 2026-11-10T17:05:02.404310 |

**Answer:**
```
The employee leave policies are outlined in several documents, covering different aspects and regions. Here’s a comprehensive overview:

1. **General Leave Policies**:  
   - Employees are encouraged to review the company’s [Leave Policies](/handbook/people-group/time-off-and-absence/leave-types/) and [country-specific leave information](/handbook/total-rewards/benefits/general-and-entity-benefits/) for detailed guidance [doc_hr_0030].  
   - For U.S.-based employees, specific leave policies are...
```

**Citations:**
1. `doc_hr_0030` — Leave of Absence Toolkit for Team Members and Managers (score: 0.1801)
2. `doc_general_0096` — People Policies - GitLab Inc (USA) (score: 0.1726)
3. `doc_sales_0086` — Sales Development (score: 0.1674)
4. `doc_general_0065` — GitLab GmbH (Germany) information & benefits (score: 0.1647)

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:11:40.238565 |

**Answer:**
```

```

---

### EL-008: What benefits are offered to employees?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 41064ms |
| Relevance | 20.00% |
| Citations | 4 |
| Timestamp | 2026-11-10T17:05:37.733470 |

**Answer:**
```
GitLab offers a comprehensive benefits package designed to support employees at every stage of life, with a focus on clarity and accessibility. Here’s a breakdown of the benefits based on the provided sources:

**1. Globally Aligned, Locally Relevant Benefits:**
   - GitLab takes a country-specific approach to benefits, ensuring they meet local statutory requirements, market standards, and cultural needs [doc_hr_0031].
   - Core offerings include medical, life, and pension benefits, provided thr...
```

**Citations:**
1. `doc_hr_0031` — Benefits (score: 0.7842)
2. `doc_hr_0049` — General & Entity Specific Benefits & Information (score: 0.6116)
3. `doc_hr_0050` — GitLab Inc (US) Benefits (score: 0.8087)
4. `doc_hr_0035` — GitLab BV (Netherlands) Benefits (score: 0.5431)

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 51090ms |
| Relevance | 40.00% |
| Citations | 3 |
| Timestamp | 2026-11-10T17:11:36.540547 |

**Answer:**
```
GitLab offers a range of benefits to its employees, focusing on mental health, remote work advantages, and comprehensive coverage for life's various needs. Here’s a detailed breakdown:

1. **Mental Health Support**:  
   - GitLab prioritizes mental health by offering resources to improve well-being and productivity. This includes advocacy through the Mental Health Team Member Advocacy Group (TMAG) [doc_general_1560].  

2. **Remote Work Benefits**:  
   - All-remote and remote-first models provi...
```

**Citations:**
1. `doc_general_1560` — GitLab Mental Health Team Member Advocacy Group (TMAG) (score: 0.8946)
2. `doc_general_1512` — The definitive guide to all-remote work and its drawbacks (score: 0.3335)
3. `doc_general_0065` — GitLab GmbH (Germany) information & benefits (score: 0.4901)

---

### EL-009: What is the drug-free workplace policy?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 12412ms |
| Relevance | 100.00% |
| Citations | 1 |
| Timestamp | 2026-11-10T17:05:14.816937 |

**Answer:**
```
GitLab's drug-free workplace policy prohibits the illegal use, possession, sale, or distribution of alcohol or controlled substances. It also mandates that legal or illegal substances must not impair an individual's job performance. This policy aims to maintain operational efficiency, ensure proper customer service, and comply with local laws in team members' residence and travel locations [doc_general_0097].
```

**Citations:**
1. `doc_general_0097` — People Policies (score: 0.5639)

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 8909ms |
| Relevance | 100.00% |
| Citations | 1 |
| Timestamp | 2026-11-10T17:11:34.289937 |

**Answer:**
```
GitLab maintains a drug-free workplace policy that prohibits the illegal use, possession, sale, or distribution of alcohol or controlled substances. This policy ensures that substances, whether legal or illegal, are not used in a way that impairs an individual's ability to perform their assigned tasks, thereby maintaining operational efficiency and ensuring proper customer service. Team members are required to comply with the local laws of their residence and any locations they travel to for com...
```

**Citations:**
1. `doc_general_0097` — People Policies (score: 0.5639)

---

### EL-010: What is the security incident response process?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:06:09.900389 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 11265ms |
| Relevance | 75.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:11:45.564630 |

**Answer:**
```
The security incident response process at GitLab involves several key steps and teams to ensure a coordinated and efficient response. Here’s a comprehensive overview based on the provided sources:

1. **Initial Detection and Reporting**:  
   - If a security incident is suspected, immediate actions are required, such as changing passwords and revoking active sessions [doc_general_0930].  
   - Notify the GitLab Security team via Slack (`#security-help` channel) or follow the [Security Incident R...
```

**Citations:**
1. `doc_general_0930` — Reclaim.ai (score: 0.8364)
2. `doc_general_0659` — AI Continuity Plan (score: 0.9974)
3. `doc_general_0124` — Support Incident Response Framework (score: 0.9949)
4. `doc_general_0440` — How to be a Support Leader on the Hook (SLOTH 🦥) (score: 0.4530)
5. `doc_general_0371` — Emergency Exception Workflow (score: 0.8318)

---

### EL-011: What are the laptop security configuration standards?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:06:14.824898 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:12:36.557873 |

**Answer:**
```

```

---

### EL-012: What is the Okta Verify setup process?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:06:37.745796 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 27540ms |
| Relevance | 50.00% |
| Citations | 2 |
| Timestamp | 2026-11-10T17:12:07.778768 |

**Answer:**
```
The Okta Verify setup process involves several steps across different devices and scenarios, as outlined in the provided sources. Here’s a comprehensive guide:

### **Manual Setup (General)** [doc_general_0921]:
1. **Prerequisite**: Ensure you have an Okta passkey saved on your phone.
2. **Download App**: Download the Okta Verify app from the App Store (Apple) or Play Store (Android).
3. **Open App**: Open the Okta Verify app.  
   - If first-time use: Select **Get started** and proceed until th...
```

**Citations:**
1. `doc_general_0921` — GitLab IT - Mobile Device Onboarding (score: 0.9999)
2. `doc_general_0922` — GitLab IT Onboarding 101 (score: 0.9973)

---

### EL-013: What is GitLab's approach to automated dependency updates?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 17190ms |
| Relevance | 75.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:06:27.090530 |

**Answer:**
```
The provided sources do not mention GitLab's approach to automated dependency updates. Instead, they cover automated dependency updates in a general engineering context [doc_engineering_0674], including design and implementation details [doc_engineering_0674], triggering via SBOM-ingestion scan profiles [doc_engineering_1203], and the use of external services like dependencies.io for automatic updates [doc_engineering_0288]. They also discuss security workflows for dependency updates [doc_it_sec...
```

**Citations:**
1. `doc_engineering_0674` — Automated dependency updates (score: 0.9998)
2. `doc_engineering_1203` — Automated Dependency Updates ADR 002: Trigger via SBOM-ingestion scan profile (score: 0.9971)
3. `doc_engineering_0288` — Distribution Team Infrastructure and Maintenance (score: 0.9924)
4. `doc_it_security_0220` — Security Dashboard Review (score: 0.9857)
5. `doc_general_1207` — Professional Services EM Scoping - CI/CD Pipeline Migration (score: 0.9804)

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 16989ms |
| Relevance | 75.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:12:02.554500 |

**Answer:**
```
GitLab's approach to automated dependency updates is multifaceted, focusing on security, integration, and open-source contributions. Here’s a comprehensive overview based on the provided sources:

1. **Dependency Scanning and Security**:  
   GitLab offers built-in **Dependency Scanning** to identify vulnerabilities in project dependencies. This feature is integrated into GitLab CI/CD pipelines and can be configured using a dedicated template [doc_general_0495]. The scanning results are accessib...
```

**Citations:**
1. `doc_general_0495` — Sec Support Pod (score: 0.1713)
2. `doc_general_0039` — Our stewardship of GitLab (score: 0.0785)
3. `doc_general_1207` — Professional Services EM Scoping - CI/CD Pipeline Migration (score: 0.9804)
4. `doc_general_0762` — Advantages of a single application (score: 0.1394)
5. `doc_general_0965` — Claude (score: 0.0504)

---

### EL-014: What are the product principles at GitLab?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 26393ms |
| Relevance | 50.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:06:41.218241 |

**Answer:**
```
GitLab's product principles are rooted in the company's **strategy and philosophy for product development** [doc_general_0099], emphasizing a **values-driven approach** [doc_engineering_0018, doc_general_0142]. These principles are built upon **GitLab Values** [doc_engineering_0018, doc_general_0142], which guide decision-making and ensure alignment with the company's culture [doc_engineering_0018].  

Key product principles include:  
1. **Iteration**: Emphasizing continuous improvement and lea...
```

**Citations:**
1. `doc_general_0099` — Product Handbook (score: 0.9999)
2. `doc_engineering_0018` — Engineering Principles (score: 0.9994)
3. `doc_general_0098` — Product Principles (score: 0.9970)
4. `doc_it_security_0185` — Product Security Engineering (score: 0.9942)
5. `doc_general_0124` — Support Incident Response Framework (score: 0.9881)

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 48750ms |
| Relevance | 50.00% |
| Citations | 6 |
| Timestamp | 2026-11-10T17:12:51.305211 |

**Answer:**
```
GitLab's product principles encompass several key areas, including strategy, philosophy, and specific guidelines for product development. Here’s a comprehensive overview based on the provided sources:

1. **Product Principles Overview**: The [Product Principles](/handbook/product/product-principles/) section outlines GitLab's strategy and philosophy regarding product development, emphasizing the company's approach to building and improving products [doc_general_0099].

2. **Component Principles*...
```

**Citations:**
1. `doc_general_0099` — Product Handbook (score: 0.9999)
2. `doc_general_0098` — Product Principles (score: 0.9970)
3. `doc_general_0187` — Product Design (score: 0.9927)
4. `doc_general_0142` — GitLab Values (score: 0.9969)
5. `doc_general_1424` — High Performing Teams and Product Division (score: 0.9940)
... and 1 more

---

### EL-015: What is the Duo messaging service architecture?

**Category:** Easy Lookup

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:07:27.098493 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 22843ms |
| Relevance | 100.00% |
| Citations | 3 |
| Timestamp | 2026-11-10T17:12:30.621512 |

**Answer:**
```
The provided sources do not contain information about the Duo messaging service architecture. They primarily cover GitLab Duo's features, use cases, and related platforms such as the Duo Agent Platform [doc_general_0273, doc_general_0251, doc_general_1378], data insights [doc_general_0746], issue reporting [doc_general_0600], and support initiatives [doc_general_0478]. If you have questions about GitLab Duo's functionality or related processes, feel free to ask.
```

**Citations:**
1. `doc_general_0746` — Product Data Insights Data Models Cheat Sheet (score: 0.5262)
2. `doc_general_0600` — DAP Rapid — Field Issue Reporting (score: 0.1979)
3. `doc_general_0478` — AI Support Pod (score: 0.0072)

---

### CS-001: What security frameworks and standards does GitLab follow?

**Category:** Cross Doc Synthesis

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 16391ms |
| Relevance | 60.00% |
| Citations | 6 |
| Timestamp | 2026-11-10T17:06:54.137710 |

**Answer:**
```
GitLab adheres to several security frameworks and standards to ensure accountability, fairness, and transparency in its operations and communications with stakeholders. Here are the key frameworks and standards identified across the sources:

1. **Governance, Risk, and Compliance (GRC) Framework**  
   GitLab's security governance discipline follows a GRC framework to define, train, and measure security strategies and progress toward security objectives. This ensures accountability, fairness, an...
```

**Citations:**
1. `doc_it_security_0120` — Security Governance Program (score: 0.9947)
2. `doc_it_security_0064` — Change Management Policy (score: 0.9932)
3. `doc_hr_0002` — GitLab Internal Acceptable Use Policy (score: 0.9921)
4. `doc_it_security_0050` — GitLab Security Logging Standards (score: 0.9835)
5. `doc_it_security_0044` — GitLab Cryptography Standard (score: 0.9805)
... and 1 more

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 21701ms |
| Relevance | 80.00% |
| Citations | 6 |
| Timestamp | 2026-11-10T17:12:52.322870 |

**Answer:**
```
GitLab adheres to several security frameworks and standards to ensure robust data protection and compliance. Here’s a comprehensive overview based on the provided sources:

1. **SAFE Framework**: GitLab Legal has developed the SAFE framework to guide team members on determining which information is internal-only and which can be shared publicly. This framework helps comply with Regulation Fair Disclosure [doc_general_0694]. The Data Team also follows the SAFE Framework for handling SAFE Data, so...
```

**Citations:**
1. `doc_general_0694` — Product Manager SAFE Guidance (score: 0.9910)
2. `doc_general_1029` — SAFE Data Guide (score: 0.9737)
3. `doc_general_0357` — Handling data as a Support Engineer (score: 0.8200)
4. `doc_general_1370` — Infrastructure Standards (score: 0.9899)
5. `doc_general_0660` — GitLab Model Vendor Selection Guidelines (score: 0.9780)
... and 1 more

---

### CS-002: How does GitLab handle employee onboarding and training?

**Category:** Cross Doc Synthesis

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:07:41.234280 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 12905ms |
| Relevance | 50.00% |
| Citations | 3 |
| Timestamp | 2026-11-10T17:12:49.462826 |

**Answer:**
```
GitLab's onboarding process is designed to be **self-driven, asynchronous, and remote-friendly**, leveraging their own collaboration tool and comprehensive documentation [doc_general_1522]. 
 Here's a breakdown:

**Process & Structure:**

* **GitLab Issues:** Onboarding tasks are completed within a standardized **GitLab issue template**, ensuring consistency and structure [doc_general_1522]. This issue acts as a central hub for the onboarding journey.

* **Self-Driven & Asynchronous:**  New hire...
```

**Citations:**
1. `doc_general_1522` — The complete guide to remote onboarding for new-hires (score: 0.9978)
2. `doc_general_1646` — Acquisition Integration (score: 0.9955)
3. `doc_general_0549` — Becoming and Being an ASE (score: 0.9945)

---

### CS-003: What are the key engineering practices and standards?

**Category:** Cross Doc Synthesis

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:07:54.158084 |

**Answer:**
```

```

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 4907ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:12:54.369672 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

### CS-004: What IT and security tools does GitLab use for employees?

**Category:** Cross Doc Synthesis

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 44031ms |
| Relevance | 40.00% |
| Citations | 3 |
| Timestamp | 2026-11-10T17:08:11.129926 |

**Answer:**
```
GitLab employs a range of IT and security tools for employees, focusing on application security, secure design, and operational efficiency. Here’s a comprehensive overview based on the provided sources:

1. **Application Security Tools**:  
   GitLab utilizes its own [Application Security Tools](https://docs.gitlab.com/ee/user/application_security/) across various internal projects as part of its [dogfooding effort](/handbook/product/product-processes/dogfooding-for-r-d/) [doc_it_security_0183, ...
```

**Citations:**
1. `doc_engineering_0445` — Sec Section (score: 0.9837)
2. `doc_it_security_0193` — Security Research (score: 0.9670)
3. `doc_general_0778` — Recruitment Privacy Policy (score: 0.9296)

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:13:51.316809 |

**Answer:**
```

```

---

### CS-005: What is GitLab's approach to work-life balance and employee well-being?

**Category:** Cross Doc Synthesis

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:08:41.747856 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 52940ms |
| Relevance | 60.00% |
| Citations | 4 |
| Timestamp | 2026-11-10T17:13:45.262700 |

**Answer:**
```
GitLab prioritizes work-life balance and employee well-being through a combination of remote work policies, asynchronous communication, and a focus on empathy and mental health.

**Remote Work & Flexibility:**
 GitLab is a fully remote company, allowing employees to work from anywhere in the world with flexible hours [doc_general_0763, doc_general_0779]. This eliminates commute time and provides autonomy over work schedules, contributing to a better work-life balance.
 A dedicated "Remote Work C...
```

**Citations:**
1. `doc_general_0763` — GitLab France S.A.S. Remote Work Charter (score: 0.8742)
2. `doc_general_1520` — Combating burnout, isolation, and anxiety in the remote workplace (score: 0.1164)
3. `doc_general_1510` — How to be a great remote manager - the complete guide (score: 0.1180)
4. `doc_general_1557` — Neurodivergence and NeuroInclusion at GitLab (score: 0.8753)

---

### PB-001: What restricted security policies exist?

**Category:** Permission Boundary

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:08:54.347588 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:13:54.381448 |

**Answer:**
```

```

---

### PB-002: What confidential contracts are in the system?

**Category:** Permission Boundary

#### admin (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 3176ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:08:14.306448 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 8600ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:13:53.863059 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

### PB-003: Show me all internal engineering documents

**Category:** Permission Boundary

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:09:14.319499 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:14:51.837638 |

**Answer:**
```

```

---

### PB-004: What are the fault tolerance standards?

**Category:** Permission Boundary

#### admin (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 3273ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:08:45.021699 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:14:53.877218 |

**Answer:**
```

```

---

### PB-005: What database security policies are in place?

**Category:** Permission Boundary

#### admin

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:09:45.030233 |

**Answer:**
```

```

#### intern

| Field | Value |
|-------|-------|
| Status | ❌ Error |
| Latency | 0ms |
| Relevance | 0.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:14:54.594893 |

**Answer:**
```

```

---

### EC-001: What is the stock price of Apple?

**Category:** Edge Case

#### admin

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 33990ms |
| Relevance | 100.00% |
| Citations | 5 |
| Timestamp | 2026-11-10T17:09:28.337780 |

**Answer:**
```
The sources do not provide a current stock price for Apple. However, they do offer some relevant financial information:

* **[doc_finance_0075]** Apple's 10-K filing for 2025 mentions the average price paid per share during specific repurchase periods in 2025, with the latest period ending August 30, 2025, showing an average price of $210.43. This is not the current stock price but indicates a historical trading range.

The other sources ([doc_hr_0027], [doc_legal_0158], [doc_legal_0124], [doc_l...
```

**Citations:**
1. `doc_finance_0075` — Apple 10-K (2025-09-27) (score: 0.5137)
2. `doc_hr_0027` — Equity Compensation (score: 0.0010)
3. `doc_legal_0158` — Execution version (score: 0.0007)
4. `doc_legal_0124` — Exhibit 1.1 (score: 0.0005)
5. `doc_legal_0625` — Exhibit 1.1 (score: 0.0005)

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 6036ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:14:57.873780 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

### EC-002: Who is the CEO of Microsoft?

**Category:** Edge Case

#### admin (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 5724ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:09:20.044045 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 6718ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:15:00.595688 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

### EC-003: asdfghjkl

**Category:** Edge Case

#### admin (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 4401ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:09:24.445118 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 6135ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:15:00.730829 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

### EC-004: Tell me everything

**Category:** Edge Case

#### admin (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 4095ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:09:28.540185 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 6339ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:15:04.212789 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

### EC-005: What happened in 1999?

**Category:** Edge Case

#### admin (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 3382ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:09:31.719589 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

#### intern (refused)

| Field | Value |
|-------|-------|
| Status | ✅ Success |
| Latency | 7513ms |
| Relevance | 100.00% |
| Citations | 0 |
| Timestamp | 2026-11-10T17:15:08.108698 |

**Answer:**
```
I couldn't find anything relevant in your authorized documents for that question. Try rephrasing it with more specific terms, such as the exact policy name or topic.
```

---

*Report generated by Vault Evaluation Framework*
