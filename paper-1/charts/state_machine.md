stateDiagram-v2
    [*] --> open: transaction_open
    open --> tentatively_closed: transaction_close (monitor)
    tentatively_closed --> closed: transaction_close (validator)
    open --> aborted: timeout
    tentatively_closed --> aborted: timeout
    open --> verified_aborted: coordinator update
    tentatively_closed --> verified_aborted: coordinator update
    closed --> [*]
    aborted --> [*]
    verified_aborted --> [*]
```

**How the Transaction State Machine Works:**

The `ktx-aggregate` service builds a state machine for each transaction to track its lifecycle.

1.  A transaction enters the `open` state when a `transaction_open` event is received.
2.  When the `monitor` consumer sees a `transaction_close` event, the state transitions to `tentatively_closed`.
3.  When the `validator` consumer sees the same `transaction_close` event, the state transitions to `closed`, and the transaction is considered successful.
4.  If a transaction remains in the `open` or `tentatively_closed` state for too long, it is moved to the `aborted` state.
5.  If the `CoordinatorCollector` reports that a transaction is no longer active on the broker, but it has not been confirmed as `closed`, it is moved to the `verified_aborted` state.
