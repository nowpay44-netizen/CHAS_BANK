CHASBANK COMPLETE DEMO - ADMIN CONTROL UPGRADE

This project is a local-only banking-style UI simulation. It uses virtual demo credits and does not connect to real banks, payment rails, or real money.

START
1. Double-click start_chasbank.bat
2. Open http://127.0.0.1:5000
3. Admin login: admin / admin123
4. Customer signup: create any demo account from Create account

ADMIN FEATURES
- Automatically lists every customer who registers through the local signup page.
- Shows registration timestamp, status and demo balance.
- Generate virtual funds on the administrator demo balance.
- Credit or debit a customer demo balance.
- Set a customer's demo balance.
- Enable/disable customer accounts.
- Create explicit credit/debit history entries for a customer.
- View customer transaction history, transfer activity and receipt references.
- Read, reply to and close customer service messages.

CUSTOMER FEATURES
- Starts at $0.00 demo balance.
- Admin-funded credits.
- Demo withdrawal with 4-digit PIN.
- Demo bank-transfer form with beneficiary, bank, routing code and account number.
- Saves completed demo beneficiaries.
- Generates a printable successful-transfer receipt/reference.

BANK SEARCH / ROUTING
The transfer form provides a small built-in demo bank directory and allows a demo routing code to be entered. It does NOT look up or submit transfers to real banks.

SECURITY
Passwords are stored as hashes and are not displayed to the administrator. Before any non-demo deployment, use a proper authentication system, HTTPS, CSRF protection, secure secret management, audit logging, and a legitimate regulated payment/banking provider.
