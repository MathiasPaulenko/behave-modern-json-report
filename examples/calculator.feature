Feature: Calculator

  As a user
  I want to perform arithmetic operations
  So that I can verify my calculations

  @smoke
  Scenario: Add two numbers
    Given I have entered 5 into the calculator
    And I have entered 7 into the calculator
    When I press add
    Then the result should be 12 on the screen

  @regression
  Scenario: Subtract two numbers
    Given I have entered 10 into the calculator
    And I have entered 4 into the calculator
    When I press subtract
    Then the result should be 6 on the screen

  @outline
  Scenario Outline: Add multiple numbers
    Given I have entered <a> into the calculator
    And I have entered <b> into the calculator
    When I press add
    Then the result should be <result> on the screen

    Examples:
      | a  | b  | result |
      | 1  | 2  | 3      |
      | 10 | 20 | 30     |
      | -1 | 1  | 0      |
