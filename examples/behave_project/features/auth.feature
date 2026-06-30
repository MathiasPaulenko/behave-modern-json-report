Feature: User Authentication
  As a registered user
  I want to log in and out
  So that I can access protected resources

  Rule: Password must be at least 8 characters

  @smoke
  Scenario: Successful login with valid credentials
    Given a user "alice" with password "secret123"
    When the user logs in with "alice" and "secret123"
    Then the user should be authenticated
    And the session token should not be empty

  @regression
  Scenario: Failed login with wrong password
    Given a user "bob" with password "correct-horse"
    When the user logs in with "bob" and "wrong-password"
    Then the user should not be authenticated
    And the error message should be "Invalid credentials"

  @regression
  Scenario: Password too short is rejected
    Given a user "charlie" with password "short"
    When the user tries to register with "charlie" and "short"
    Then registration should fail
    And the error message should be "Password must be at least 8 characters"
