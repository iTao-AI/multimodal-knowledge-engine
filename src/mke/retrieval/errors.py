"""Path-neutral retrieval authority failures."""


class RetrievalAuthorityError(RuntimeError):
    """Active retrieval candidates violate stable locator authority."""

    problem = "retrieval_authority_invalid"
    cause = "active retrieval candidates contain duplicate stable Evidence locators"
    next_step = "restore_valid_database_or_reingest_into_new_database"
