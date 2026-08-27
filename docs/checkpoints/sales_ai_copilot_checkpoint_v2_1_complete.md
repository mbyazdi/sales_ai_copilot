# Sales AI Copilot — Development Checkpoint

**Checkpoint:** V2.1 Complete  
**Continuation Point:** V2.2 — Sales Rep Daily Workspace V2  
**Date:** 2026-08-24

---

## 1. Project

**Project name:** `sales_ai_copilot`

**Repository:** `https://github.com/mbyazdi/sales_ai_copilot.git`

**Main branch:** `main`

**Development environments:**
- Windows
- PowerShell
- VS Code
- Python virtualenv
- Django
- SQLite Demo DB

**Current Git state at latest sync:**
- `HEAD = 2c3e168`
- `origin/main = 2c3e168`
- working tree was clean before final V2.1 browser validation

Recent commits:
- `2c3e168 Update demo database credentials`
- `89d3ddd Add Sales AI Copilot V2 checkpoint`
- `fdfae1d Add role-aware manager and sales rep experience`
- `80276fc Add recommendation explainability drill-down`
- `aaf58b9 Add explainability quality monitoring`

---

## 2. Business Context / North Star

This project is a Demo for a trading/distribution company with roughly:
- ~700 field sales reps / visitors
- several thousand customers
- multiple business lines across the country

For the Demo, the **Electrical line** was selected because scope is smaller.

Example product families:
- Personal electrical: shaver, hair dryer, etc.
- Home electrical: blender, fan, TV, etc.

Field sales reps follow a predefined daily/monthly visit plan and visit assigned customers to take orders.

The product goal is **not a chatbot demo**. The goal is a Sales AI Copilot that helps each rep improve real sales performance during customer visits.

Primary business objectives:
1. Increase sales volume
2. Increase basket size / sell more products
3. Help reps achieve monthly product/category/line targets
4. Preserve customer fit / acceptance / satisfaction

The intended decision flow is:

```text
Customer Context
+ Purchase Behavior
+ Customer Grade
+ Recommendation
+ Promotion
+ Sales Rep Target
+ Inventory
+ Previous Visit / Outcome / Follow-up
        ↓
Commercial Decision Layer
        ↓
Prioritized Opportunity
        ↓
Next Best Action
        ↓
Talking Point
        ↓
Sales Rep Execution
        ↓
Outcome / Follow-up
        ↓
Feedback
        ↓
Next Recommendation
```

Important architectural distinction:

```text
Recommendation Engine
"What fits this customer?"
        ↓
Commercial Decision Layer
"What should this rep focus on now?"
        ↓
Next Best Action
"What should the rep do?"
        ↓
AI Copilot
"How can I help the rep execute it?"
```

The LLM is **not** the authoritative business decision source.

---

## 3. Product Experience Separation

### Manager Experience
Expected focus:
- Team overview
- Sales / conversion
- Target achievement
- Visit performance
- Follow-up health
- Recommendation performance
- Explainability / diagnostics
- Recommendation tuning
- Promotion effectiveness
- Trends / exceptions

### Sales Rep Daily Workspace
Expected focus:
- Today’s visit plan
- My customers
- Visit statuses
- Customer priority
- Pre-visit brief
- Open follow-ups
- Target gap relevance
- Quick entry into customer workspace

### Customer Visit / Sales Meeting Workspace
Expected focus:
- Customer brief
- Recommendations
- Sales opportunity
- Promotion
- Target relevance
- Inventory relevance
- Talking Point
- Next Best Action
- Outcome
- Follow-up
- Context-aware Copilot

---

## 4. Development Workflow Preferences

When giving code changes, ALWAYS provide:

```text
FILE
OPEN — with Ctrl+P and exact path
FIND — exact text/code
ADD / REPLACE / DELETE
RUN validation commands
```

Do not instruct manual browsing of VS Code tree.

For Django shell multi-line tests ALWAYS use:

```powershell
python manage.py shell
```

Then send the whole test using:

```python
exec(