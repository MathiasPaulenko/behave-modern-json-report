Feature: Calculator
  As a user
  I want to perform arithmetic operations
  So that I can verify my calculations

  Background:
    Given a calculator is turned on

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

  @smoke @fast
  Scenario: Multiply two numbers
    Given I have entered 3 into the calculator
    And I have entered 4 into the calculator
    When I press multiply
    Then the result should be 12 on the screen

  @regression
  Scenario: Divide two numbers
    Given I have entered 20 into the calculator
    And I have entered 4 into the calculator
    When I press divide
    Then the result should be 5 on the screen

  @regression
  Scenario: Division by zero produces an error
    Given I have entered 5 into the calculator
    And I have entered 0 into the calculator
    When I press divide
    Then the calculator should show "Cannot divide by zero"

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
