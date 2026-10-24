# DriveEase Car Rental System

A local Flask website connected to Microsoft SQL Server. Includes customer car browsing, date/time booking requests, an admin login/dashboard, booking approval, customer listing, and basic car status management.

## Requirements
- Python 3.10+
- Microsoft SQL Server / SQL Server Express with database `CarRentalDB`
- Microsoft ODBC Driver 18 for SQL Server
- The five existing tables: `Cars`, `Customers`, `Bookings`, `Rentals`, and `AdminUsers`

## Expected table columns
The app uses the schema supplied for this project:
- `Cars(CarID, CarName, ModelYear, CarType, PricePerDay, Status)`
- `Customers(CustomerID, FullName, Email, Phone, LicenseNumber, CreatedAt)`
- `Bookings(BookingID, CarID, CustomerID, PickupDate, PickupTime, ReturnDate, ReturnTime, TotalAmount, BookingStatus, CreatedAt)`
- `Rentals(RentalID, CarID, CustomerName, CustomerPhone, StartDate, EndDate, TotalAmount, RentalStatus, BookingDate)`
- `AdminUsers(AdminID, Username, PasswordHash, CreatedAt)`

The application does not drop, recreate, or alter your tables. Primary key IDs should be configured as identity/auto-generated columns. The `Rentals` table is read only for availability checks; new customer requests are inserted into `Bookings`.

## Run in PyCharm (Windows)
1. Open the extracted `DriveEase_Car_Rental_System` folder as a PyCharm project.
2. Open PyCharm Terminal and create a virtual environment if needed: `python -m venv .venv`
3. Activate it: `.venv\\Scripts\\activate`
4. Install packages: `python -m pip install -r requirements.txt`
5. Verify `db.py` uses your SQL Server instance. Default is `PRARTHANA\\SQLEXPRESS`, database `CarRentalDB`, Windows Authentication.
6. In SSMS, verify the five tables and their columns are present and your Windows account has database access.
7. Create your own admin login: `python create_admin.py`. Choose a username and password of at least 10 characters. The password is stored as a hash.
8. Run `app.py` in PyCharm.
9. Open `http://127.0.0.1:5000/` for the customer website or `http://127.0.0.1:5000/admin/login` for admin.

## Booking behavior
- Customer submissions are stored with status `Pending`; they are not automatically approved.
- The total is calculated by calendar-day difference, minimum one day, multiplied by the daily rate. Same-day rentals therefore cost one day.
- Availability checks active overlapping `Bookings` and date-only `Rentals`. Cancelled/rejected bookings and cancelled/returned/completed rentals do not block dates.
- Car `Status` is treated as a maintenance/unavailable override, not changed to `Booked` after a request. This avoids making a vehicle globally unavailable for dates unrelated to a booking.
- This is a learning/demo app. Before public deployment, add CSRF protection, rate limiting, stricter validation, privacy notices, and production server configuration. Do not commit credentials or `.env` files to GitHub.

## Troubleshooting
- `No module named flask`: install packages in the same PyCharm interpreter used to run `app.py`.
- ODBC driver error: install Microsoft ODBC Driver 18 for SQL Server.
- SQL connection failure: verify SQL Server service/instance, Windows Authentication permissions, and `DB_SERVER` / `DB_NAME` in `db.py`.
- SQL column error: compare the live database columns with the schema above; this project intentionally does not modify existing tables.

## Deployment note
`127.0.0.1` is local to your computer. A hosted version needs a reachable hosted SQL Server or secure network connection; do not expose your home SQL Server directly to the internet.

## Customer site and private admin area

The public customer website starts at `/`. Customers can browse cars and submit booking requests there. The public navigation does not expose the admin dashboard.

Admin pages are separate routes in the same Flask application:

- Login: `http://127.0.0.1:5000/admin/login`
- Dashboard: `http://127.0.0.1:5000/admin`
- Logout: `http://127.0.0.1:5000/admin/logout`

The dashboard and admin actions are protected by the `admin_required` server-side session check. Visiting `/admin` without logging in redirects to the login page. Create an admin account using `python create_admin.py` before logging in. Customers only see the public pages; the same backend and database process their bookings for the admin to review.

For public deployment, set a strong random `FLASK_SECRET_KEY` environment variable and configure a database server reachable by the deployed application. Do not expose your local SQL Server directly to the internet.

## Separate customer login and admin login

The project now has separate customer and admin authentication:

- Customer registration: `http://127.0.0.1:5000/customer/register`
- Customer login: `http://127.0.0.1:5000/customer/login`
- Customer booking history: `http://127.0.0.1:5000/customer/bookings`
- Customer logout: `/customer/logout`
- Admin login: `http://127.0.0.1:5000/admin/login`
- Admin dashboard: `http://127.0.0.1:5000/admin`

### One-time database setup for customer accounts

1. Open SQL Server Management Studio and connect to `PRARTHANA\SQLEXPRESS` using Windows Authentication.
2. Open the file `sql/create_customer_accounts.sql` from this project.
3. Confirm the script targets `CarRentalDB`, then click **Execute**.
4. This is an additive migration: it creates `dbo.CustomerAccounts` only if it does not already exist. It does not delete or overwrite existing customers, cars, or bookings.
5. Restart the Flask app and visit `/customer/register` to create a customer account.

The customer account table stores Werkzeug password hashes, not plain-text passwords. Existing customer records remain intact; if a customer registers with an email already in `dbo.Customers` and no account exists for that customer, the account is linked to that existing customer record. Booking requests require customer sign-in and use the signed-in customer's ID rather than trusting profile details submitted from the browser. Customers can only view bookings associated with their own CustomerID.

Customer and admin sessions are separate role paths; signing into either portal clears the previous session. Keep the admin URL private, use a strong `FLASK_SECRET_KEY` in your environment for anything beyond local development, and do not expose your local SQL Server directly to the internet.
