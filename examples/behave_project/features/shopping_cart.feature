Feature: Shopping Cart
  As a shopper
  I want to manage my cart
  So that I can purchase items

  Background:
    Given an empty shopping cart

  @smoke
  Scenario: Add a single item to the cart
    When I add "Laptop" priced at $999 to the cart
    Then the cart should contain 1 items
    And the cart total should be $999

  @regression
  Scenario: Add multiple items and check total
    When I add "Mouse" priced at $25 to the cart
    And I add "Keyboard" priced at $50 to the cart
    Then the cart should contain 2 items
    And the cart total should be $75

  @regression
  Scenario: Remove an item from the cart
    Given I add "Headphones" priced at $100 to the cart
    When I remove "Headphones" from the cart
    Then the cart should contain 0 items
    And the cart total should be $0

  @smoke
  Scenario: Apply a discount code
    When I add "Monitor" priced at $300 to the cart
    And I apply the discount code "SAVE10"
    Then the cart total should be $270
