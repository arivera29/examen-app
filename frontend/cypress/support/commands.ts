/// <reference types="cypress" />

declare global {
  namespace Cypress {
    interface Chainable {
      login(email: string, password: string): Chainable<void>;
    }
  }
}

Cypress.Commands.add('login', (email: string, password: string) => {
  cy.request('POST', 'http://localhost:8000/api/v1/auth/register', {
    email,
    password,
    full_name: 'E2E User',
  });
  cy.request('POST', 'http://localhost:8000/api/v1/auth/login', { email, password }).then((resp) => {
    window.localStorage.setItem('access_token', resp.body.access_token);
  });
});

export {};
