from datetime import datetime, date, time
from decimal import Decimal, ROUND_CEILING
from functools import wraps
import os

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_connection

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-local-development-key")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("customer_id"):
            flash("Please sign in with your customer account to continue.", "error")
            return redirect(url_for("customer_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def fetch_car(cursor, car_id):
    cursor.execute("SELECT CarID, CarName, ModelYear, CarType, PricePerDay, Status FROM dbo.Cars WHERE CarID = ?", car_id)
    return cursor.fetchone()


def car_available(cursor, car_id, pickup_dt, return_dt):
    """Check requested interval against active bookings and date-only legacy rentals."""
    cursor.execute("""
        SELECT COUNT(*) FROM dbo.Bookings
        WHERE CarID = ?
          AND LOWER(COALESCE(BookingStatus, 'pending')) NOT IN ('cancelled', 'canceled', 'rejected')
          AND (PickupDate < ? OR (PickupDate = ? AND PickupTime < ?))
          AND (ReturnDate > ? OR (ReturnDate = ? AND ReturnTime > ?))
    """, car_id, return_dt.date(), return_dt.date(), return_dt.time(), pickup_dt.date(), pickup_dt.date(), pickup_dt.time())
    booking_overlap = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM dbo.Rentals
        WHERE CarID = ?
          AND LOWER(COALESCE(RentalStatus, 'active')) NOT IN ('cancelled', 'canceled', 'returned', 'completed', 'rejected')
          AND StartDate < ? AND EndDate >= ?
    """, car_id, return_dt.date(), pickup_dt.date())
    rental_overlap = cursor.fetchone()[0]
    return booking_overlap == 0 and rental_overlap == 0


@app.route("/")
def home():
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT CarID, CarName, ModelYear, CarType, PricePerDay, Status FROM dbo.Cars ORDER BY CarID")
        cars = cursor.fetchall()
        return render_template("index.html", cars=cars)
    except Exception:
        app.logger.exception("Unable to load car list")
        return render_template("index.html", cars=[], db_error=True)
    finally:
        if connection:
            connection.close()


@app.route("/customer/register", methods=["GET", "POST"])
def customer_register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        license_number = request.form.get("license_number", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not all([full_name, email, phone, license_number, password, confirm]):
            flash("Please complete every field.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
        else:
            connection = None
            try:
                connection = get_connection()
                cursor = connection.cursor()
                cursor.execute("SELECT CustomerID, FullName, Phone, LicenseNumber FROM dbo.Customers WHERE LOWER(Email) = ?", email)
                customer = cursor.fetchone()
                if customer:
                    customer_id = customer.CustomerID
                    cursor.execute("SELECT CustomerID FROM dbo.CustomerAccounts WHERE CustomerID = ?", customer_id)
                    if cursor.fetchone():
                        flash("An account already exists for this email. Please sign in.", "error")
                    else:
                        cursor.execute("UPDATE dbo.Customers SET FullName=?, Phone=?, LicenseNumber=? WHERE CustomerID=?", full_name, phone, license_number, customer_id)
                        cursor.execute("INSERT INTO dbo.CustomerAccounts (CustomerID, PasswordHash, CreatedAt) VALUES (?, ?, SYSDATETIME())", customer_id, generate_password_hash(password))
                        connection.commit()
                        session.clear()
                        session["customer_id"] = customer_id
                        session["customer_name"] = full_name
                        flash("Your customer account has been created.", "success")
                        return redirect(url_for("home"))
                else:
                    cursor.execute("INSERT INTO dbo.Customers (FullName, Email, Phone, LicenseNumber, CreatedAt) OUTPUT INSERTED.CustomerID VALUES (?, ?, ?, ?, SYSDATETIME())", full_name, email, phone, license_number)
                    customer_id = cursor.fetchone()[0]
                    cursor.execute("INSERT INTO dbo.CustomerAccounts (CustomerID, PasswordHash, CreatedAt) VALUES (?, ?, SYSDATETIME())", customer_id, generate_password_hash(password))
                    connection.commit()
                    session.clear()
                    session["customer_id"] = customer_id
                    session["customer_name"] = full_name
                    flash("Your customer account has been created.", "success")
                    return redirect(url_for("home"))
            except Exception:
                if connection:
                    connection.rollback()
                app.logger.exception("Customer registration failed")
                flash("Could not create your account. Confirm the CustomerAccounts migration has been run and try again.", "error")
            finally:
                if connection:
                    connection.close()
    return render_template("customer_register.html")


@app.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        connection = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT c.CustomerID, c.FullName, a.PasswordHash FROM dbo.Customers c INNER JOIN dbo.CustomerAccounts a ON a.CustomerID=c.CustomerID WHERE LOWER(c.Email)=?", email)
            row = cursor.fetchone()
            if row and check_password_hash(str(row.PasswordHash), password):
                session.clear()
                session["customer_id"] = row.CustomerID
                session["customer_name"] = row.FullName
                next_url = request.args.get("next", "")
                if next_url.startswith("/") and not next_url.startswith("//") and not next_url.startswith("/admin"):
                    return redirect(next_url)
                return redirect(url_for("home"))
            flash("Incorrect email or password.", "error")
        except Exception:
            app.logger.exception("Customer login failed")
            flash("Unable to sign in. Confirm the CustomerAccounts migration has been run.", "error")
        finally:
            if connection:
                connection.close()
    return render_template("customer_login.html")


@app.route("/customer/logout")
def customer_logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/customer/bookings")
@customer_required
def customer_bookings():
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("""SELECT b.BookingID, c.CarName, b.PickupDate, b.PickupTime, b.ReturnDate,
                                 b.ReturnTime, b.TotalAmount, b.BookingStatus, b.CreatedAt
                          FROM dbo.Bookings b LEFT JOIN dbo.Cars c ON c.CarID=b.CarID
                          WHERE b.CustomerID=? ORDER BY b.CreatedAt DESC, b.BookingID DESC""", session["customer_id"])
        bookings = cursor.fetchall()
        return render_template("customer_bookings.html", bookings=bookings)
    except Exception:
        app.logger.exception("Customer bookings could not be loaded")
        flash("Could not load your bookings.", "error")
        return redirect(url_for("home"))
    finally:
        if connection:
            connection.close()


@app.route("/book/<int:car_id>")
@customer_required
def booking_page(car_id):
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        car = fetch_car(cursor, car_id)
        if not car:
            abort(404)
        cursor.execute("SELECT CustomerID, FullName, Email, Phone, LicenseNumber FROM dbo.Customers WHERE CustomerID=?", session["customer_id"])
        customer = cursor.fetchone()
        if not customer:
            session.clear()
            flash("Please sign in again.", "error")
            return redirect(url_for("customer_login"))
        return render_template("booking.html", car=car, customer=customer, today=date.today().isoformat())
    except Exception:
        app.logger.exception("Unable to open booking form")
        flash("We could not load this car. Check the database connection and try again.", "error")
        return redirect(url_for("home"))
    finally:
        if connection:
            connection.close()


@app.route("/create-booking", methods=["POST"])
@customer_required
def create_booking():
    required = ["car_id", "pickup_date", "pickup_time", "return_date", "return_time"]
    values = {key: request.form.get(key, "").strip() for key in required}
    if any(not values[key] for key in required):
        flash("Please complete every field.", "error")
        return redirect(url_for("booking_page", car_id=values.get("car_id", "")))
    try:
        car_id = int(values["car_id"])
        pickup_dt = datetime.strptime(values["pickup_date"] + " " + values["pickup_time"], "%Y-%m-%d %H:%M")
        return_dt = datetime.strptime(values["return_date"] + " " + values["return_time"], "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        flash("Please enter valid dates and times.", "error")
        return redirect(url_for("home"))
    if pickup_dt < datetime.now().replace(second=0, microsecond=0):
        flash("Pickup must be in the future.", "error")
        return redirect(url_for("booking_page", car_id=car_id))
    if return_dt <= pickup_dt:
        flash("Return date and time must be after pickup.", "error")
        return redirect(url_for("booking_page", car_id=car_id))
    # Billing is by calendar day, with a minimum charge of one day.
    days = max(1, (return_dt.date() - pickup_dt.date()).days)
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT CarID, CarName, PricePerDay, Status FROM dbo.Cars WITH (UPDLOCK, HOLDLOCK) WHERE CarID = ?", car_id)
        car = cursor.fetchone()
        if not car:
            flash("That car could not be found.", "error")
            return redirect(url_for("home"))
        if str(car.Status).strip().lower() in {"maintenance", "unavailable", "inactive", "booked"}:
            flash("This vehicle is currently unavailable.", "error")
            return redirect(url_for("home"))
        if not car_available(cursor, car_id, pickup_dt, return_dt):
            flash("That car is already booked for some or all of those dates. Please choose another period.", "error")
            return redirect(url_for("booking_page", car_id=car_id))
        cursor.execute("SELECT CustomerID, FullName FROM dbo.Customers WHERE CustomerID = ?", session["customer_id"])
        customer = cursor.fetchone()
        if not customer:
            session.clear()
            flash("Please sign in again before booking.", "error")
            return redirect(url_for("customer_login"))
        customer_id = customer.CustomerID
        total = (Decimal(str(car.PricePerDay)) * days).quantize(Decimal("0.01"))
        cursor.execute("""INSERT INTO dbo.Bookings
            (CarID, CustomerID, PickupDate, PickupTime, ReturnDate, ReturnTime, TotalAmount, BookingStatus, CreatedAt)
            OUTPUT INSERTED.BookingID VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', SYSDATETIME())""",
            car_id, customer_id, pickup_dt.date(), pickup_dt.time(), return_dt.date(), return_dt.time(), total)
        booking_id = cursor.fetchone()[0]
        connection.commit()
        return render_template("booking_success.html", booking_id=booking_id, car_name=car.CarName, total_amount=total,
                               pickup_dt=pickup_dt, return_dt=return_dt, days=days)
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Booking creation failed")
        flash("We couldn't save the booking. Please check the database tables and try again.", "error")
        return redirect(url_for("booking_page", car_id=car_id))
    finally:
        if connection:
            connection.close()


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        connection = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT AdminID, Username, PasswordHash FROM dbo.AdminUsers WHERE Username = ?", username)
            row = cursor.fetchone()
            valid = False
            if row:
                stored = str(row.PasswordHash or "")
                try:
                    valid = check_password_hash(stored, password)
                except (ValueError, TypeError):
                    valid = False
                # Support an old plain-text local demo record once, then upgrade it to a hash.
                if not valid and stored == password and password:
                    valid = True
                    cursor.execute("UPDATE dbo.AdminUsers SET PasswordHash = ? WHERE AdminID = ?", generate_password_hash(password), row.AdminID)
                    connection.commit()
            if valid:
                session.clear()
                session["admin_id"] = row.AdminID
                session["admin_username"] = row.Username
                return redirect(url_for("admin_dashboard"))
            flash("Incorrect username or password.", "error")
        except Exception:
            app.logger.exception("Admin login failed")
            flash("Unable to log in. Check your database connection and AdminUsers table.", "error")
        finally:
            if connection:
                connection.close()
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM dbo.Cars")
        car_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dbo.Customers")
        customer_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dbo.Bookings WHERE LOWER(COALESCE(BookingStatus,'')) = 'pending'")
        pending_count = cursor.fetchone()[0]
        cursor.execute("""SELECT b.BookingID, b.CarID, c.CarName, cu.FullName, cu.Email, cu.Phone,
                                 b.PickupDate, b.PickupTime, b.ReturnDate, b.ReturnTime,
                                 b.TotalAmount, b.BookingStatus, b.CreatedAt
                          FROM dbo.Bookings b
                          LEFT JOIN dbo.Cars c ON c.CarID=b.CarID
                          LEFT JOIN dbo.Customers cu ON cu.CustomerID=b.CustomerID
                          ORDER BY b.CreatedAt DESC, b.BookingID DESC""")
        bookings = cursor.fetchall()
        cursor.execute("SELECT CarID, CarName, ModelYear, CarType, PricePerDay, Status FROM dbo.Cars ORDER BY CarID")
        cars = cursor.fetchall()
        cursor.execute("SELECT CustomerID, FullName, Email, Phone, LicenseNumber, CreatedAt FROM dbo.Customers ORDER BY CreatedAt DESC")
        customers = cursor.fetchall()
        return render_template("admin_dashboard.html", bookings=bookings, cars=cars, customers=customers,
                               car_count=car_count, customer_count=customer_count, pending_count=pending_count)
    except Exception:
        app.logger.exception("Admin dashboard failed")
        return "Could not load admin dashboard. Confirm the database schema matches the README.", 500
    finally:
        if connection:
            connection.close()


@app.route("/admin/booking/<int:booking_id>/<action>", methods=["POST"])
@admin_required
def update_booking(booking_id, action):
    allowed = {"confirm": "Confirmed", "cancel": "Cancelled", "reject": "Rejected"}
    if action not in allowed:
        abort(404)
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE dbo.Bookings SET BookingStatus = ? WHERE BookingID = ?", allowed[action], booking_id)
        if cursor.rowcount == 0:
            connection.rollback()
            flash("Booking not found.", "error")
        else:
            connection.commit()
            flash(f"Booking #{booking_id} updated to {allowed[action]}.", "success")
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Booking status update failed")
        flash("Could not update booking status.", "error")
    finally:
        if connection:
            connection.close()
    return redirect(url_for("admin_dashboard") + "#bookings")


@app.route("/admin/car/add", methods=["POST"])
@admin_required
def add_car():
    name = request.form.get("car_name", "").strip()
    car_type = request.form.get("car_type", "").strip()
    status = request.form.get("status", "Available").strip()
    try:
        year = int(request.form.get("model_year", ""))
        price = Decimal(request.form.get("price_per_day", ""))
        if not name or not car_type or year < 1900 or price <= 0 or status not in {"Available", "Maintenance", "Unavailable"}:
            raise ValueError
        connection = get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO dbo.Cars (CarName, ModelYear, CarType, PricePerDay, Status) VALUES (?, ?, ?, ?, ?)", name, year, car_type, price, status)
            connection.commit()
        finally:
            connection.close()
        flash("Car added successfully.", "success")
    except Exception:
        app.logger.exception("Add car failed")
        flash("Could not add car. Check the entered values and database schema.", "error")
    return redirect(url_for("admin_dashboard") + "#cars-admin")


@app.route("/admin/car/<int:car_id>/status", methods=["POST"])
@admin_required
def update_car_status(car_id):
    status = request.form.get("status", "")
    if status not in {"Available", "Maintenance", "Unavailable"}:
        abort(400)
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE dbo.Cars SET Status = ? WHERE CarID = ?", status, car_id)
        connection.commit()
        flash("Car status updated.", "success")
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Car status update failed")
        flash("Could not update car status.", "error")
    finally:
        if connection:
            connection.close()
    return redirect(url_for("admin_dashboard") + "#cars-admin")


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)

