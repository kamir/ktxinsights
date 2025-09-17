# TASK-4: Create a "Hanging Transaction" Test Scenario

To provide a concrete, quantitative comparison with other monitoring tools, we need a test scenario that highlights the unique capabilities of `ktxinsights`.

**Action:** Create a new test scenario called `04_hanging_transaction`. This scenario will simulate a transaction that opens but never closes, and it will be designed so that it does *not* trigger any alerts in standard monitoring tools like KMinion (e.g., no consumer lag, no unusual throughput).

### 4. Baseline Comparison

This is the most critical point. The paper makes claims of superiority, but it doesn't currently provide a concrete, quantitative comparison.

*   **Plan:** I will create a new test scenario called `04_hanging_transaction`. This scenario will simulate a transaction that opens but never closes, and it will be designed so that it does *not* trigger any alerts in standard monitoring tools like KMinion (e.g., no consumer lag, no unusual throughput). I will then:
    1.  Create a new local analysis script for this scenario.
    2.  Add a new appendix to the paper that shows the output of `ktx-compare` for this scenario, clearly identifying the aborted transaction.
    3.  In the same appendix, I will include screenshots or example output from a tool like KMinion or the Confluent Control Center, showing that they do *not* detect this issue.
    4.  I will add a detailed explanation of why `ktxinsights` is able to catch this type of "business-level" failure while the other tools, which focus on infrastructure-level metrics, cannot.

This will provide a powerful, concrete demonstration of the value of the `ktxinsights` approach.
