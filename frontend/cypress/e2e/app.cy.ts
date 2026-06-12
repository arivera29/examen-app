describe('Examen App E2E', () => {
  it('should load login page', () => {
    cy.visit('/login');
    cy.contains('Iniciar sesión');
    cy.get('input[formControlName="email"]').should('exist');
    cy.get('input[formControlName="password"]').should('exist');
  });

  it('should navigate to register', () => {
    cy.visit('/login');
    cy.contains('Crear cuenta').click();
    cy.url().should('include', '/register');
    cy.contains('Crear cuenta');
  });
});
