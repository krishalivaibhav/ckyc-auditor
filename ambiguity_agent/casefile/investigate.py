"""SNEHA. Plan/execute loop. MUST be able to answer INSUFFICIENT_EVIDENCE."""


def investigate(customer, candidate, signal) -> list:
    raise NotImplementedError("resolve a name-only match against context. "
                              "emit Evidence[] with status CONFIRMED|CORRELATED|MISSING.")
