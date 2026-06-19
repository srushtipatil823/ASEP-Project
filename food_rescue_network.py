# Part 1/4
from ui_theme import load_theme
import streamlit as st
from email_utils import send_email
import sqlite3
import hashlib
from datetime import datetime, timedelta
import pandas as pd

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="Smart Food Rescue Network",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)



# ==========================================
# DATABASE
# ==========================================
conn = sqlite3.connect("food_rescue.db", check_same_thread=False, timeout=30)
conn.execute("PRAGMA journal_mode=WAL;")

ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

ROLES = [
    "Donor",
    "Volunteer",
    "NGO / Trust",
    "Waste-to-Energy Partner"
]

STATUSES = [
    "Uploaded",
    "Assigned",
    "Picked Up",
    "Safe",
    "Delivered",
    "Spoiled",
    "Processed"
]

PROCESSING_METHODS = ["Biogas", "Compost"]


# ==========================================
# HELPERS
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def execute_query(query, params=(), fetch=False, fetchone=False):
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    if fetchone:
        return cur.fetchone()
    if fetch:
        return cur.fetchall()
    return None


def normalize_location(location):
    return (location or "").strip().lower()


def get_users_by_role_and_location(role, location):
    return execute_query(
        "SELECT * FROM users WHERE role=?",
        (role,),
        fetch=True
    ) and [
        user for user in execute_query(
            "SELECT * FROM users WHERE role=?",
            (role,),
            fetch=True
        )
        if normalize_location(user[4]) == normalize_location(location)
    ]


def estimate_safe_until(food_type):
    food = (food_type or "").lower()
    if any(x in food for x in ["rice", "curry", "roti", "cooked"]):
        hours = 6
    elif "packed" in food:
        hours = 12
    elif any(x in food for x in ["snack", "dry"]):
        hours = 24
    else:
        hours = 8
    return datetime.now() + timedelta(hours=hours)


def add_notification(recipient_email, message):
    execute_query(
        "INSERT INTO notifications (recipient_email, message) VALUES (?, ?)",
        (recipient_email, message)
    )


def add_tracking_log(food_post_id, status, user_email, remarks=""):
    execute_query(
        """
        INSERT INTO tracking_logs
        (food_post_id, status, user_email, remarks)
        VALUES (?, ?, ?, ?)
        """,
        (food_post_id, status, user_email, remarks)
    )


def get_unread_notification_count(email):
    row = execute_query(
        "SELECT COUNT(*) FROM notifications WHERE recipient_email=? AND is_read=0",
        (email,),
        fetchone=True
    )
    return row[0] if row else 0


def get_user_by_email(email):
    return execute_query(
        "SELECT * FROM users WHERE email=?",
        (email,),
        fetchone=True
    )


def login_user(email, password):

    user = execute_query(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, hash_password(password)),
        fetchone=True
    )

    if user and user[8] == 1:
        return "BLOCKED"

    return user


def role_icon(role):
    return {
        "Admin": "🛠️",
        "Donor": "🎁",
        "Volunteer": "🚚",
        "NGO / Trust": "🏢",
        "Waste-to-Energy Partner": "♻️"
    }.get(role, "👤")


# ==========================================
# DATABASE SETUP
# ==========================================
def ensure_column(table, column, definition):
    cols = [r[1] for r in execute_query(f"PRAGMA table_info({table})", fetch=True)]
    if column not in cols:
        execute_query(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def create_tables():
    execute_query("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            location TEXT,
            contact1 TEXT,
            contact2 TEXT,
            role TEXT,
            is_blocked INTEGER DEFAULT 0,
            reports_count INTEGER DEFAULT 0       
        )
    """)

    execute_query("""
        CREATE TABLE IF NOT EXISTS food_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_email TEXT,
            food_type TEXT,
            meals INTEGER,
            quantity TEXT,
            prep_time TEXT,
            pickup_location TEXT,
            notes TEXT,
            safe_until TEXT,
            status TEXT DEFAULT 'Uploaded',
            processing_method TEXT,
            assigned_volunteer TEXT,
            assigned_ngo TEXT,
            assigned_energy_partner TEXT,
            created_at TEXT DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    for col in [
        ("processing_method", "TEXT"),
        ("assigned_volunteer", "TEXT"),
        ("assigned_ngo", "TEXT"),
        ("assigned_energy_partner", "TEXT")
    ]:
        ensure_column("food_posts", col[0], col[1])
    ensure_column(
        "food_posts",
        "tentative_spoil_time",
        "TEXT"
    )

    ensure_column(
        "food_posts",
        "pickup_map_link",
        "TEXT"
    )    

    ensure_column(
        "food_posts",
        "prep_date",
        "TEXT"
    )

    ensure_column(
        "food_posts",
        "spoil_date",
        "TEXT"
    )
    ensure_column("users", "is_blocked", "INTEGER DEFAULT 0")
    ensure_column("users", "reports_count", "INTEGER DEFAULT 0")

    execute_query("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    execute_query("""
        CREATE TABLE IF NOT EXISTS volunteer_help_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_post_id INTEGER,
            volunteer_email TEXT,
            message TEXT,
            timestamp TEXT DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    execute_query("""
        CREATE TABLE IF NOT EXISTS ngo_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_post_id INTEGER,
            ngo_email TEXT,
            message TEXT,
            timestamp TEXT DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    execute_query("""
        CREATE TABLE IF NOT EXISTS energy_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_post_id INTEGER,
            partner_email TEXT,
            processing_method TEXT,
            timestamp TEXT DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    execute_query("""
        CREATE TABLE IF NOT EXISTS tracking_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_post_id INTEGER,
            status TEXT,
            user_email TEXT,
            remarks TEXT,
            timestamp TEXT DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)
    execute_query("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_email TEXT,
        reported_email TEXT,
        food_post_id INTEGER,
        created_at TEXT DEFAULT (
            datetime('now', '+5 hours', '+30 minutes')
        )
    )
""")

def create_admin():
    if not get_user_by_email(ADMIN_EMAIL):
        execute_query(
            """
            INSERT INTO users
            (name, email, password, location, contact1, contact2, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Admin",
                ADMIN_EMAIL,
                hash_password(ADMIN_PASSWORD),
                "Pune",
                "9999999999",
                "",
                "Admin"
            )
        )


def init_session():
    defaults = {
        "logged_in": False,
        "user": None,
        "current_page": "dashboard",
        "profile_updated": False
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    saved_email = st.query_params.get("email")

    if (
        saved_email
        and not st.session_state.logged_in
    ):
        user = get_user_by_email(saved_email)

        if user and user[8] == 0:
            st.session_state.logged_in = True

            st.session_state.user = {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "location": user[4],
                "role": user[7]
            }   
def go_to(page):
    st.session_state.current_page = page
    st.rerun()


def logout():
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.current_page = "dashboard"
    st.query_params.clear()
    st.rerun()


# ==========================================
# AUTH
# ==========================================
def login_page():
    
    st.markdown(
        "<h1 style='text-align:center;'>🍽️ Smart Food Rescue Network</h1>",
        unsafe_allow_html=True
    )

    st.markdown(
    f"""
    <img src="https://plus.unsplash.com/premium_photo-1683141173692-aba4763bce41?fm=jpg&q=60&w=3000&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8Z2l2aW5nJTIwZm9vZHxlbnwwfHwwfHx8MA%3D%3D"
    style="
    width:100%;
    height:350px;
    object-fit:cover;
    border-radius:20px;">
    """,
    unsafe_allow_html=True
)

    

    st.markdown(
        "<h3 style='text-align:center;'>Rescue Food • Feed People • Save Energy</h3>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<p style='text-align:center;font-size:18px;'>Connecting Donors, Volunteers, NGOs and Waste-to-Energy Partners through one platform.</p>",
        unsafe_allow_html=True
    )

    # Show all authentication options in tabs instead of sidebar
    login_tab, register_tab, forgot_tab = st.tabs([
        "🔐 Login",
        "📝 Register",
        "🔑 Change Password"
    ])

    # ======================================================
    # LOGIN TAB
    # ======================================================
    with login_tab:
        email = st.text_input("Email", key="login_email")
        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button("Login", key="login_button"):
            user = login_user(email, password)

            if user == "BLOCKED":
                st.error("Your account has been blocked by admin.")

            elif user:
                st.session_state.logged_in = True

                st.session_state.user = {
                    "id": user[0],
                    "name": user[1],
                    "email": user[2],
                    "location": user[4],
                    "role": user[7]
                }

                st.query_params["email"] = user[2]
                st.session_state.current_page = "dashboard"
                st.rerun()
            else:
                st.error("Invalid email or password.")

    # ======================================================
    # REGISTER TAB
    # ======================================================
    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Full Name")
            reg_email = st.text_input("Email")
            reg_password = st.text_input(
                "Password",
                type="password"
            )
            confirm_password = st.text_input(
                "Confirm Password",
                type="password"
            )
            location = st.text_input(
    "District / City Name",
    help="Use only standard district or city name. Example: Pune, Mumbai, Nashik"
)
            contact1 = st.text_input("Contact Number 1")
            contact2 = st.text_input("Contact Number 2 (Optional)")
            role = st.selectbox("Role", ROLES)

            register_submit = st.form_submit_button("Register")

        if register_submit:
            if not all([
                name,
                reg_email,
                reg_password,
                confirm_password,
                location,
                contact1
            ]):
                st.error("Please fill all required fields.")
            elif reg_password != confirm_password:
                st.error("Passwords do not match.")

            elif len(reg_password) < 6:
                st.error("Password must be at least 6 characters long.")
            elif "@" not in reg_email or "." not in reg_email:
                st.error("Please enter a valid email address.")                
            elif get_user_by_email(reg_email):
                st.error("Email already exists.")

            else:

                email_sent = send_email(
                    reg_email,
                    "Welcome to Smart Food Rescue Network",
                    f"""
Hello {name},

Welcome to Smart Food Rescue Network.

Your account has been created successfully as:
{role}

Location:
{location}

Thank you for joining our food rescue mission.
"""
                )
                
                if email_sent:

                    try:
                        execute_query(
                            """
                            INSERT INTO users
                            (
                                name,
                                email,
                                password,
                                location,
                                contact1,
                                contact2,
                                role
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                name,
                                reg_email,
                                hash_password(reg_password),
                                location,
                                contact1,
                                contact2,
                                role
                            )
                        )

                        st.success(
                            "Registration successful. "
                            "Please check your email."
                        )

                    except sqlite3.IntegrityError:
                        st.error("Email already exists.")

                else:
                    st.error(
                        "Invalid or unreachable email address."
                    )
    # ======================================================
    # FORGOT PASSWORD TAB
    # ======================================================
    with forgot_tab:
        reset_email = st.text_input(
            "Registered Email",
            key="reset_email"
        )
        current_password = st.text_input(
    "Current Password",
    type="password",
    key="current_password"
)
        new_password = st.text_input(
            "New Password",
            type="password",
            key="reset_password"
        )
        confirm_new_password = st.text_input(
            "Confirm New Password",
            type="password",
            key="reset_confirm_password"
        )

        if st.button("Change Password", key="reset_button"):

            user = get_user_by_email(reset_email)

            if not user:
                st.error("Email not found.")

            elif hash_password(current_password) != user[3]:
                st.error("Current password is incorrect.")

            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters long.")

            elif new_password != confirm_new_password:
                st.error("Passwords do not match.")

            else:
                execute_query(
            """
            UPDATE users
            SET password = ?
            WHERE email = ?
            """,
            (
                hash_password(new_password),
                reset_email
            )
        )

                st.success(
                    "Password changed successfully. "
                    "Please login with your new password."
        )

# ==========================================
# COMMON PAGES
# ==========================================


def edit_profile():
    st.title("✏️ Edit Profile")
    user = get_user_by_email(st.session_state.user["email"])

    with st.form("edit_profile"):
        name = st.text_input("Full Name", value=user[1])
        location = st.text_input("Location", value=user[4] or "")
        contact1 = st.text_input("Contact Number 1", value=user[5] or "")
        contact2 = st.text_input("Contact Number 2", value=user[6] or "")

        if user[7] == "Admin":
            st.text_input("Role", value="Admin", disabled=True)
            role = "Admin"
        else:
            role = st.selectbox(
                "Role",
                ROLES,
                index=ROLES.index(user[7]) if user[7] in ROLES else 0
            )

        current_password = st.text_input(
            "Current Password",
            type="password"
        )

        col1, col2 = st.columns(2)
        save = col1.form_submit_button("Save")
        
    
    if save:
        if hash_password(current_password) != user[3]:
            st.error("Incorrect password")
        else:
            execute_query(
                """
                UPDATE users
                SET name=?, location=?, contact1=?, contact2=?, role=?
                WHERE email=?
                """,
                (name, location, contact1, contact2, role, user[2])
            )
            st.session_state.user["name"] = name
            st.session_state.user["location"] = location
            st.session_state.user["role"] = role
            st.success("Profile updated successfully")
            


def report_issue():
    st.title("🐞 Report Issue")
    with st.form("report_issue"):
        subject = st.text_input("Subject")
        description = st.text_area("Description")
        col1, col2 = st.columns(2)
        submit = col1.form_submit_button("Submit")
       
    

    if submit:
        user = st.session_state.user
        add_notification(
            ADMIN_EMAIL,
            f"Issue from {user['name']} ({user['email']})\nSubject: {subject}\n\n{description}"
        )
        st.success("Issue reported successfully")


def notifications_page():
    st.title("🔔 Notifications")
    rows = execute_query(
        """
        SELECT id, message, is_read, timestamp
        FROM notifications
        WHERE recipient_email=?
        ORDER BY id DESC
        """,
        (st.session_state.user["email"],),
        fetch=True
    )

    if not rows:
        st.info("No notifications")

    for row in rows:
        st.write(f"**{row[3]}**")
        st.write(row[1])
        if row[2] == 0 and st.button(f"Mark as Read {row[0]}"):
            execute_query(
                "UPDATE notifications SET is_read=1 WHERE id=?",
                (row[0],)
            )
            st.rerun()
        st.markdown("---")

    


def contact_support():
    st.title("📞 Contact & Support")

    roles = ["All", "Admin"] + ROLES
    role_filter = st.selectbox("Filter by Role", roles)
    location_filter = st.text_input("Filter by Location")

    users = execute_query(
        "SELECT name, role, location, contact1, email FROM users",
        fetch=True
    )

    filtered = []
    for u in users:
        if role_filter != "All" and u[1] != role_filter:
            continue
        if location_filter and normalize_location(u[2]) != normalize_location(location_filter):
            continue
        filtered.append(u)

    if filtered:
        st.dataframe(
            pd.DataFrame(
                filtered,
                columns=["Name", "Role", "Location", "Contact", "Email"]
            ),
            use_container_width=True
        )

    if st.button(
    "🚨 Emergency Contact Admin",
    key="contact_support_emergency_btn"):

        admin = get_user_by_email(ADMIN_EMAIL)
        st.info(
            f"Name: {admin[1]}\nEmail: {admin[2]}\nContact: {admin[5]}"
        )

    
# ==========================================
# ROLE DASHBOARDS
# ==========================================
def donor_dashboard():
    st.title("🎁 Donor Dashboard")
    if "food_uploaded" not in st.session_state:
        st.session_state.food_uploaded = False

    tabs = st.tabs(["Upload Food", "My Posts", "Notifications", "Support"])

    # ======================================================
    # TAB 1: Upload Food
    # ======================================================
    with tabs[0]:
        if st.session_state.food_uploaded:

            st.success("Food uploaded successfully.")

            st.info(
                "Recommendation: Volunteer and NGO should physically "
                "recheck the food before distribution."
            )

            st.stop()     
        with st.form("upload_food"):
            food_type = st.text_input(
                "Food Type",
                key="food_type"
            )
            meals = st.number_input(
                "Number of Meals",
                min_value=1,
                value=1,
                key="meals"
            )
            quantity = st.text_input(
                "Quantity",
                key="quantity"
            )
            prep_date = st.date_input(
                "Food Prepared Date"
            )

            prep_time = st.text_input(
                "Food Prepared At (AM/PM)",
                key="prep_time",
                placeholder="07:00 AM"
            )

            spoil_date = st.date_input(
                "Tentative Spoil Date"
            )

            tentative_spoil_time = st.text_input(
                "Tentative Spoil Time (AM/PM)",
                key="tentative_spoil_time",
                placeholder="09:30 PM"
            )
            pickup_location = st.text_input(
                "District / City Name",
                value=st.session_state.user["location"],
                help="Use only standard district or city name. Example: Pune, Mumbai, Nashik",
                key="pickup_location"
            )
            pickup_map_link = st.text_input(
                "Google Maps Link (Optional)",
                placeholder="https://maps.app.goo.gl/..."
            )            
            notes = st.text_area(
                "Additional Notes",
                key="notes"
            )
            submit = st.form_submit_button(
                "Upload Food",
                disabled=st.session_state.get(
                    "upload_in_progress",
                    False
                )
            )
        if submit:

            if st.session_state.get(
                "upload_in_progress",
                False
            ):
                st.stop()

            st.session_state.upload_in_progress = True

            # safe_until = estimate_safe_until(food_type)
            try:

                prep_dt = datetime.strptime(
                    f"{prep_date} {prep_time}",
                    "%Y-%m-%d %I:%M %p"
                )

                spoil_dt = datetime.strptime(
                    f"{spoil_date} {tentative_spoil_time}",
                    "%Y-%m-%d %I:%M %p"
                )

                if spoil_dt <= prep_dt:
                    st.error(
                        "Tentative spoil date/time must be after preparation date/time."
                    )
                    st.stop()            
            except ValueError:

                st.error(
                    "Please enter time in HH:MM AM/PM format.\n"
                    "Example: 07:00 AM or 09:30 PM"
                )

                st.session_state.upload_in_progress = False
                st.stop()                    

            execute_query(
                """
                INSERT INTO food_posts
                (
                    donor_email,
                    food_type,
                    meals,
                    quantity,
                    prep_time,
                    prep_date,
                    pickup_location,
                    pickup_map_link,
                    notes,
                    tentative_spoil_time,
                    spoil_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    st.session_state.user["email"],
                    food_type,
                    meals,
                    quantity,
                    prep_time,
                    str(prep_date),
                    pickup_location,
                    pickup_map_link,
                    notes,
                    tentative_spoil_time,
                    str(spoil_date)
                )
            )

            post_id = execute_query(
                "SELECT MAX(id) FROM food_posts",
                fetchone=True
            )[0]

            add_tracking_log(
                post_id,
                "Uploaded",
                st.session_state.user["email"]
            )

            # Notify nearby volunteers
            volunteers = get_users_by_role_and_location(
                "Volunteer",
                pickup_location
            )

            for volunteer in volunteers:
                add_notification(
                    volunteer[2],
                    f"New food donation available near you. Post #{post_id}."
                )


            for volunteer in volunteers:
                send_email(
                    volunteer[2],
                    "New Food Donation Available",
                    f"""
Hello Volunteer,

A new food donation is available near your area.

Food Type: {food_type}
Meals: {meals}
Quantity: {quantity}
Pickup Location: {pickup_location}

Please login to Smart Food Rescue Network application.

Thank you.
"""
                )                
                        

            st.session_state.upload_in_progress = False
            st.session_state.food_uploaded = True
            st.rerun()

    # ======================================================
    # TAB 2: My Posts
    # ======================================================
    with tabs[1]:
        # Track which post is being edited
        if "editing_post_id" not in st.session_state:
            st.session_state.editing_post_id = None

        posts = execute_query(
            """
            SELECT
            id,
            food_type,
            meals,
            quantity,
            prep_date,
            prep_time,
            spoil_date,
            tentative_spoil_time,
            pickup_location,
            notes,
            status,
            assigned_volunteer
            FROM food_posts
            WHERE donor_email = ?
            ORDER BY id DESC
            """,
            (st.session_state.user["email"],),
            fetch=True
        )

        if not posts:
            st.info("You have not uploaded any food posts yet.")
        else:
            for post in posts:
                (
                post_id,
                food_type,
                meals,
                quantity,
                prep_date,
                prep_time,
                spoil_date,
                tentative_spoil_time,
                pickup_location,
                notes,
                status,
                assigned_volunteer
                ) = post

                with st.expander(
                    f"Post #{post_id} - {food_type} ({status})",
                    expanded=False
                ):
                    # Display post details
                    st.write(f"**Food Type:** {food_type}")
                    st.write(f"**Number of Meals:** {meals}")
                    st.write(f"**Quantity:** {quantity}")
                    st.write(
                        f"**Prepared On:** {prep_date} {prep_time}" 
                    )
                    st.write(f"**Pickup Location:** {pickup_location}")
                    st.write(f"**Additional Notes:** {notes or '-'}")
                    st.write(f"**Current Status:** {status}")
                    st.write(
                        f"**Tentative Spoil On:** {spoil_date} {tentative_spoil_time}"
                    )
                    st.write(
                        f"**Assigned Volunteer:** "
                        f"{assigned_volunteer if assigned_volunteer else 'Not Assigned'}"
                    )                    
                    st.markdown("---")
                    st.subheader("📍 Food Tracking Timeline")
                    if assigned_volunteer:

                        if st.button(
                            "🚨 Report Volunteer",
                            key=f"report_volunteer_{post_id}"
                        ):
                            already_reported = execute_query(
                                """
                                SELECT id
                                FROM reports
                                WHERE reporter_email = ?
                                AND reported_email = ?
                                AND food_post_id = ?
                                """,
                                (
                                    st.session_state.user["email"],
                                    assigned_volunteer,
                                    post_id
                                ),
                                fetchone=True
                            )

                            if already_reported:
                                st.warning(
                                    "You have already reported this volunteer."
                                )

                            else:
                                execute_query(
                                    """
                                    INSERT INTO reports
                                    (
                                        reporter_email,
                                        reported_email,
                                        food_post_id
                                    )
                                    VALUES (?, ?, ?)
                                    """,
                                    (
                                        st.session_state.user["email"],
                                        assigned_volunteer,
                                        post_id
                                    )
                                )

                                execute_query(
                                """
                                UPDATE users
                                SET reports_count = reports_count + 1
                                WHERE email = ?
                                """,
                                (assigned_volunteer,)
                            )

                                add_notification(
                                    ADMIN_EMAIL,
                                    f"Volunteer {assigned_volunteer} "
                                    f"was reported by donor "
                                    f"{st.session_state.user['email']} "
                                    f"for Post #{post_id}."
                                )

                                st.success(
                                    "Volunteer reported successfully."
                                )

                                st.rerun()
                    logs = execute_query(
                        """
                        SELECT
                            status,
                            user_email,
                            remarks,
                            timestamp
                        FROM tracking_logs
                        WHERE food_post_id=?
                        ORDER BY id ASC
                        """,
                        (post_id,),
                        fetch=True
                    )

                    if logs:
                        for log in logs:
                            status_log, user_log, remarks_log, time_log = log

                            st.write(
                                f"✅ {status_log} | "
                                f"{time_log}"
                            )

                            st.caption(
                                f"By: {user_log}"
                            )

                            if remarks_log:
                                st.caption(
                                    f"Remark: {remarks_log}"
                                )

                            st.write("⬇️")
                    else:
                        st.info("No tracking updates available.")

                    # Action buttons
                    col1, col2 = st.columns(2)

                    if status == "Uploaded":

                        if col1.button(
                            "📝 Edit",
                            key=f"edit_post_{post_id}"
                        ):
                            st.session_state.editing_post_id = post_id
                            st.rerun()

                        if col2.button(
                            "🗑️ Delete",
                            key=f"delete_post_{post_id}"
                        ):
                            execute_query(
                                "DELETE FROM food_posts WHERE id=?",
                                (post_id,)
                            )

                            if (
                                st.session_state.editing_post_id
                                == post_id
                            ):
                                st.session_state.editing_post_id = None

                            st.success(
                                "Post deleted successfully."
                            )

                            st.rerun()

                    else:

                        st.info(
                            "🛑 Cannot edit or delete — food is already in progress."
                        )

                    # Edit form
                    if st.session_state.editing_post_id == post_id:
                        st.markdown("---")
                        st.subheader("✏️ Edit Food Post")

                        with st.form(
                            f"edit_form_{post_id}"
                        ):
                            new_food_type = st.text_input(
                                "Food Type",
                                value=food_type
                            )

                            new_meals = st.number_input(
                                "Number of Meals",
                                min_value=1,
                                value=int(meals)
                            )

                            new_quantity = st.text_input(
                                "Quantity",
                                value=quantity or ""
                            )

                            new_prep_time = st.text_input(
                                "Food Prepared At (AM/PM)",
                                value=prep_time or "",
                                placeholder="07:00 AM"
                            )

                            new_tentative_spoil_time = st.text_input(
                                "Tentative Spoil Time (AM/PM)",
                                value=tentative_spoil_time or "",
                                placeholder="09:30 PM"
                            )

                            new_pickup_location = st.text_input(
                                "Pickup Location",
                                value=pickup_location or ""
                            )

                            new_notes = st.text_area(
                                "Additional Notes",
                                value=notes or ""
                            )

                            col_save, col_cancel = st.columns(2)

                            save_changes = (
                                col_save.form_submit_button(
                                    "Save Changes"
                                )
                            )

                            cancel_edit = (
                                col_cancel.form_submit_button(
                                    "Cancel"
                                )
                            )

                        if save_changes:
                            
                            execute_query(
                                """
                                UPDATE food_posts
                                SET
                                    food_type = ?,
                                    meals = ?,
                                    quantity = ?,
                                    prep_time = ?,
                                    pickup_location = ?,
                                    notes = ?,
                                    tentative_spoil_time = ?
                                WHERE id = ?
                                """,
                                (
                                    new_food_type,
                                    new_meals,
                                    new_quantity,
                                    new_prep_time,
                                    new_pickup_location,
                                    new_notes,
                                    new_tentative_spoil_time,
                                    post_id
                                )
                            )

                            st.session_state.editing_post_id = None
                            st.success(
                                "Food post updated successfully."
                            )
                            st.rerun()

                        if cancel_edit:
                            st.session_state.editing_post_id = None
                            st.rerun()

    # ======================================================
    # TAB 3: Notifications
    # ======================================================
    with tabs[2]:
        notifications_page()

    # ======================================================
    # TAB 4: Support
    # ======================================================
    with tabs[3]:
        contact_support()   

def volunteer_dashboard():
    st.title("🚚 Volunteer Dashboard")

    volunteer_email = st.session_state.user["email"]

    tabs = st.tabs([
        "Available Requests",
        "Notifications",
        "Support"
    ])

    # ==========================================
    # TAB 1: AVAILABLE REQUESTS
    # ==========================================
    with tabs[0]:
        # --------------------------------------    
        # Available Requests (status = Uploaded)
        # --------------------------------------
        st.subheader("📦 Available Food Requests")

        available_posts = execute_query(
            """
            SELECT
                fp.id,
                fp.donor_email,
                fp.food_type,
                fp.meals,
                fp.quantity,
                fp.prep_date,
                fp.prep_time,
                fp.spoil_date,
                fp.tentative_spoil_time,
                fp.pickup_location,
                fp.pickup_map_link,
                fp.notes,
                u.name,
                u.contact1
            FROM food_posts fp
            LEFT JOIN users u
                ON fp.donor_email = u.email
            WHERE fp.status = 'Uploaded'
            ORDER BY fp.id DESC
            """,
            fetch=True
        )

        if available_posts:
            for post in available_posts:
                (
                    post_id,
                    donor_email,
                    food_type,
                    meals,
                    quantity,
                    prep_date,
                    prep_time,
                    spoil_date,
                    tentative_spoil_time,
                    pickup_location,
                    pickup_map_link,
                    notes,
                    donor_name,
                    donor_contact
                ) = post

                with st.expander(
                    f"Post #{post_id} - {food_type} ({meals} meals)"
                ):
                    st.write(f"**Donor Name:** {donor_name or 'N/A'}")
                    st.write(f"**Donor Email:** {donor_email}")
                    st.write(f"**Donor Contact:** {donor_contact or 'N/A'}")
                    st.write(f"**Food Type:** {food_type}")
                    st.write(f"**Meals:** {meals}")
                    st.write(f"**Quantity:** {quantity}")
                    st.write(
                        f"**Prepared On:** {prep_date} {prep_time}"
                    )

                    st.write(f"**Pickup Location:** {pickup_location}")
                    
                    if pickup_map_link:
                        st.link_button(
                            "📍 Open in Google Maps",
                            pickup_map_link
                        )                    

                    st.write(
                        f"**Tentative Spoil On:** {spoil_date} {tentative_spoil_time}"
                    )

                    st.write(f"**Notes:** {notes or '-'}")

                    col1, col2 = st.columns(2)

                    # Accept Request
                    if col1.button(
                        "✅ Accept Request",
                        key=f"accept_{post_id}"
                    ):

                        current_status = execute_query(
                            """
                            SELECT status, assigned_volunteer
                            FROM food_posts
                            WHERE id=?
                            """,
                            (post_id,),
                            fetchone=True
                        )

                        if (
                            current_status
                            and current_status[0] == "Uploaded"
                            and not current_status[1]
                        ):

                            execute_query(
                                """
                                UPDATE food_posts
                                SET status='Assigned',
                                    assigned_volunteer=?
                                WHERE id=?
                                """,
                                (volunteer_email, post_id)
                            )

                            add_tracking_log(
                                post_id,
                                "Assigned",
                                volunteer_email,
                                "Volunteer accepted the request."
                            )

                            add_notification(
                                donor_email,
                                f"Volunteer has accepted your food request (Post #{post_id})."
                            )

                            send_email(
                                donor_email,
                                "Food Request Accepted",
                                f"""
Hello,

Your food donation request has been accepted.

Volunteer Email: {volunteer_email}

Food Type: {food_type}
Meals: {meals}
Pickup Location: {pickup_location}

Volunteer will contact you soon.

Thank you for helping reduce food waste.
"""
                            )

                            st.success("Request accepted successfully.")
                            st.rerun()

                        else:
                            st.warning(
                                "This request has already been accepted by another volunteer."
                            )

                    
                        
                    # Help Request
                    if col2.button(
                        "🆘 Help",
                        key=f"help_{post_id}"
                    ):

                        already_requested = execute_query(
                            """
                            SELECT id
                            FROM volunteer_help_requests
                            WHERE food_post_id = ?
                            AND volunteer_email = ?
                            """,
                            (
                                post_id,
                                volunteer_email
                            ),
                            fetchone=True
                        )

                        if already_requested:

                            st.warning(
                                "Help request already sent."
                            )

                        else:

                            execute_query(
                                """
                                INSERT INTO volunteer_help_requests
                                (
                                    food_post_id,
                                    volunteer_email,
                                    message
                                )
                                VALUES (?, ?, ?)
                                """,
                                (
                                    post_id,
                                    volunteer_email,
                                    "Volunteer requested assistance."
                                )
                            )

                            add_notification(
                                ADMIN_EMAIL,
                                f"Volunteer {volunteer_email} requested help for Post #{post_id}."
                            )

                            st.success(
                                "Help request sent to admin."
                            )

                        st.rerun()
        else:
            st.info("No available food requests.")

        # --------------------------------------
        # Assigned Requests
        # --------------------------------------
        st.subheader("🚚 My Assigned Requests")

        assigned_posts = execute_query(
            """
        SELECT
            id,
            donor_email,
            food_type,
            meals,
            quantity,
            prep_date,
            prep_time,
            spoil_date,
            pickup_location,
            pickup_map_link,
            tentative_spoil_time,
            notes,
            status
            FROM food_posts
            WHERE assigned_volunteer=?
            ORDER BY id DESC
            """,
            (volunteer_email,),
            fetch=True
        )

        if assigned_posts:
            for post in assigned_posts:
                (
                    post_id,
                    donor_email,
                    food_type,
                    meals,
                    quantity,
                    prep_date,
                    prep_time,
                    spoil_date,
                    pickup_location,
                    pickup_map_link,
                    tentative_spoil_time,
                    notes,
                    status
                ) = post

                with st.expander(
                    f"My Request #{post_id} - {food_type} ({status})"
                ):
                    st.write(f"**Food Type:** {food_type}")
                    st.write(f"**Meals:** {meals}")
                    st.write(f"**Quantity:** {quantity}")
                    st.write(
                        f"**Prepared On:** {prep_date} {prep_time}"
                    )

                    st.write(
                        f"**Pickup Location:** {pickup_location}"
                    )

                    st.write(
                        f"**Tentative Spoil On:** {spoil_date} {tentative_spoil_time}"
                    )

                    st.write(f"**Notes:** {notes or '-'}")
                    st.write(f"**Current Status:** {status}")

                    col1, col2 = st.columns(2)
                    col3, col4 = st.columns(2)

                    # Mark Picked Up
                    if status == "Assigned" and col1.button(
                        "📦 Mark Picked Up",
                        key=f"picked_{post_id}"
                    ):
                        execute_query(
                            """
                            UPDATE food_posts
                            SET status='Picked Up'
                            WHERE id=?
                            """,
                            (post_id,)
                        )

                        add_tracking_log(
                            post_id,
                            "Picked Up",
                            volunteer_email,
                            "Food picked up by volunteer."
                        )

                        add_notification(
                            donor_email,
                            f"Your food request (Post #{post_id}) has been picked up."
                        )

                        st.success("Marked as Picked Up.")
                        st.rerun()

                    # Mark Safe
                    if status == "Picked Up" and col2.button(
                        "✅ Mark Safe",
                        key=f"safe_{post_id}"
                    ):
                        execute_query(
                            """
                            UPDATE food_posts
                            SET status='Safe'
                            WHERE id=?
                            """,
                            (post_id,)
                        )

                        add_tracking_log(
                            post_id,
                            "Safe",
                            volunteer_email,
                            "Food inspected and marked safe."
                        )

                        ngos = get_users_by_role_and_location(
                            "NGO / Trust",
                            pickup_location
                        )

                        for ngo in ngos:
                            add_notification(
                                
                                ngo[2],
                                f"Safe food is available in your area (Post #{post_id})."
                            )
                            send_email(
                                ngo[2],
                                "Safe Food Available",
                                f"""
Hello NGO / Trust,

Safe food is available in your area.

Post ID: {post_id}
Food Type: {food_type}
Meals: {meals}
Pickup Location: {pickup_location}

Please login to Smart Food Rescue Network.

Thank you.
"""
                            )                            

                        st.success("Marked as Safe.")
                        st.rerun()

                    # Mark Spoiled
                    if status == "Picked Up" and col3.button(
                        "⚠️ Mark Spoiled",
                        key=f"spoiled_{post_id}"
                    ):
                        execute_query(
                            """
                            UPDATE food_posts
                            SET status='Spoiled'
                            WHERE id=?
                            """,
                            (post_id,)
                        )

                        add_tracking_log(
                            post_id,
                            "Spoiled",
                            volunteer_email,
                            "Food marked as spoiled."
                        )

                        partners = get_users_by_role_and_location(
                            "Waste-to-Energy Partner",
                            pickup_location
                        )

                        for partner in partners:
                            add_notification(
                                partner[2],
                                f"Spoiled food is available for processing (Post #{post_id})."
                            )
                            send_email(
                                partner[2],
                                "Spoiled Food Available for Processing",
                                f"""
Hello Waste-to-Energy Partner,

Spoiled food is available for processing.

Post ID: {post_id}
Food Type: {food_type}
Meals: {meals}
Pickup Location: {pickup_location}

Please login to Smart Food Rescue Network.

Thank you.
"""
                            )                            

                        st.success("Marked as Spoiled.")
                        st.rerun()

                    # Cancel Assignment
                    if status == "Assigned" and col4.button(
                        "↩️ Cancel Assignment",
                        key=f"cancel_{post_id}"
                    ):
                        execute_query(
                            """
                            UPDATE food_posts
                            SET status='Uploaded',
                                assigned_volunteer=NULL
                            WHERE id=?
                            """,
                            (post_id,)
                        )

                        add_tracking_log(
                            post_id,
                            "Uploaded",
                            volunteer_email,
                            "Volunteer cancelled assignment."
                        )

                        add_notification(
                            donor_email,
                            f"Volunteer cancelled assignment for your request (Post #{post_id})."
                        )

                        nearby_volunteers = get_users_by_role_and_location(
                            "Volunteer",
                            pickup_location
                        )

                        for volunteer in nearby_volunteers:
                            if volunteer[2] != volunteer_email:
                                add_notification(
                                    volunteer[2],
                                    f"Food request #{post_id} is available again."
                                )

                        st.success("Assignment cancelled.")
                        st.rerun()
                    already_reported = execute_query(
                        """
                        SELECT 1
                        FROM reports
                        WHERE reporter_email = ?
                        AND reported_email = ?
                        AND food_post_id = ?
                        """,
                        (
                            volunteer_email,
                            donor_email,
                            post_id
                        ),
                        fetch=True
                    )
                    # Report Donor
                    if st.button(
                        "🚨 Report Donor",
                        key=f"report_donor_{post_id}"
                    ):

                        if already_reported:
                            st.warning(
                                "You have already reported this donor."
                            )

                        else:
                            execute_query(
                                """
                                INSERT INTO reports
                                (
                                    reporter_email,
                                    reported_email,
                                    food_post_id
                                )
                                VALUES (?, ?, ?)
                                """,
                                (
                                    volunteer_email,
                                    donor_email,
                                    post_id
                                )
                            )

                            execute_query(
                                """
                                UPDATE users
                                SET reports_count = reports_count + 1
                                WHERE email = ?
                                """,
                                (donor_email,)
                            )

                            add_notification(
                                ADMIN_EMAIL,
                                f"Donor {donor_email} was reported by volunteer {volunteer_email} for Post #{post_id}."
                            )

                            st.success(
                                "Donor reported successfully."
                            )

                            st.rerun()
        else:
            st.info("No assigned requests.")
                   
                    

    # ==========================================
    # TAB 2: NOTIFICATIONS  
    # ==========================================
    with tabs[1]:
        rows = execute_query(
            """
            SELECT message, timestamp
            FROM notifications
            WHERE recipient_email=?
            ORDER BY id DESC
            """,
            (volunteer_email,),
            fetch=True
        )

        if rows:
            for message, timestamp in rows:
                st.info(f"{timestamp}\n\n{message}")
        else:
            st.info("No notifications.")

    # ==========================================
    # TAB 3: SUPPORT
    # ==========================================
    with tabs[2]:
        contact_support()


def ngo_dashboard():
    st.title("🏢 NGO Dashboard")

    ngo_email = st.session_state.user["email"]

    tabs = st.tabs([
        "Safe Food Requests",
        "Notifications",
        "Support"
    ])

    # ==========================================
    # TAB 1: SAFE FOOD REQUESTS
    # ==========================================
    with tabs[0]:
        rows = execute_query(
            """
            SELECT
    id,
    donor_email,
    food_type,
    meals,
    quantity,
    pickup_location,
    notes,
    status,
    assigned_ngo,
    assigned_volunteer
FROM food_posts
            
                WHERE status = 'Safe'
                AND (assigned_ngo IS NULL OR assigned_ngo = ?)
            ORDER BY id DESC
            """,
            (ngo_email,),
            fetch=True
        )

        if not rows:
            st.info("No safe food requests available.")
        else:
            for row in rows:
                (
    post_id,
    donor_email,
    food_type,
    meals,
    quantity,
    pickup_location,
    notes,
    status,
    assigned_ngo,
    assigned_volunteer
) = row

                with st.expander(
                    f"Post #{post_id} - {food_type} ({meals} meals)"
                ):
                    st.write(f"**Donor Email:** {donor_email}")
                    st.write(f"**Food Type:** {food_type}")
                    st.write(f"**Meals:** {meals}")
                    st.write(f"**Quantity:** {quantity}")
                    st.write(f"**Pickup Location:** {pickup_location}")
                    st.write(f"**Notes:** {notes or '-'}")
                    st.write(f"**Status:** {status}")
                    st.write(
                        f"**Assigned NGO:** "
                        f"{assigned_ngo if assigned_ngo else 'Not Assigned'}"
                    )
                    st.write(
                        f"**Assigned Volunteer:** "
                        f"{assigned_volunteer if assigned_volunteer else 'Not Assigned'}"
                                            
                    )

                    col1, col3, col4, col5 = st.columns(4)    

                    # ----------------------------------
                    # Accept
                    # ----------------------------------
                    if col1.button(
                        "✅ Accept",
                        key=f"ngo_accept_{post_id}"
                    ):

                        current_ngo = execute_query(
                            """
                            SELECT assigned_ngo
                            FROM food_posts
                            WHERE id = ?
                            """,
                            (post_id,),
                            fetchone=True
                        )

                        if not current_ngo[0]:

                            execute_query(
                                """
                                UPDATE food_posts
                                SET assigned_ngo = ?
                                WHERE id = ?
                                """,
                                (ngo_email, post_id)
                            )

                            st.success("Request accepted successfully.")

                        else:

                            st.warning(
                                "Already accepted by another NGO."
                            )

                        st.rerun()

                    

                    # ----------------------------------
                    # Help
                    # ----------------------------------
                                 
                    if col3.button(
                        "🆘 Help",
                        key=f"ngo_help_{post_id}"
                    ):
                        already_requested = execute_query(
                            """
                            SELECT id
                            FROM ngo_requests
                            WHERE food_post_id = ?
                            AND ngo_email = ?
                            """,
                            (
                                post_id,
                                ngo_email
                            ),
                            fetchone=True
                        )                        
                        if already_requested:

                            st.warning(
                                "Help request already sent."
                            )

                        else:                        
                            execute_query(
                                """
                                INSERT INTO ngo_requests
                                (food_post_id, ngo_email, message)
                                VALUES (?, ?, ?)
                                """,
                                (
                                    post_id,
                                    ngo_email,
                                    "NGO requested assistance."
                                )
                            )

                            add_notification(
                                ADMIN_EMAIL,
                                f"NGO {ngo_email} requested help "
                                f"for Post #{post_id}."
                            )

                            st.success("Help request sent to admin.")
                            st.rerun()

                    # ----------------------------------
                    # Confirm Delivery
                    # ----------------------------------
                    
                    if not assigned_ngo:

                        st.warning(
                            "Please accept this request first."
                        )

                    elif assigned_ngo != ngo_email:

                        st.warning(
                            "Only assigned NGO can confirm delivery."
                        )

                    elif col4.button(
                        "📦 Confirm Delivery",
                        key=f"ngo_deliver_{post_id}"
                    ):
                        execute_query(
                            """
                            UPDATE food_posts
                            SET status = 'Delivered',
                                assigned_ngo = ?
                            WHERE id = ?
                            """,
                            (ngo_email, post_id)
                        )

                        add_tracking_log(
                            post_id,
                            "Delivered",
                            ngo_email,
                            "Food delivered successfully by NGO."
                        )

                        add_notification(
                            donor_email,
                            f"Your food donation (Post #{post_id}) "
                            f"has been delivered successfully."
                        )
                        send_email(
                            donor_email,
                            "Food Donation Delivered Successfully",
                            f"""
Hello,

Your donated food has been delivered successfully.

Post ID: {post_id}
Food Type: {food_type}
Meals: {meals}
Pickup Location: {pickup_location}

Thank you for helping reduce hunger and food waste.

Smart Food Rescue Network
"""
                        )
                        add_notification(
                            ADMIN_EMAIL,
                            f"Food Post #{post_id} "
                            f"was delivered by NGO {ngo_email}."
                        )

                        st.success("Delivery confirmed successfully.")
                        st.rerun()
                    # ----------------------------------
                    # Report Volunteer
                    # ----------------------------------
                    already_reported = execute_query(
                        """
                        SELECT 1
                        FROM reports
                        WHERE reporter_email = ?
                        AND reported_email = ?
                        AND food_post_id = ?
                        """,
                        (
                            ngo_email,
                            assigned_volunteer,
                            post_id
                        ),
                        fetch=True
                    )                       
                    if col5.button(
                        "🚨 Report Volunteer",
                        key=f"ngo_report_{post_id}"
                    ):

                        if already_reported:

                            st.warning(
                                "You have already reported this volunteer."
                            )

                        else:

                            execute_query(
                                """
                                INSERT INTO reports
                                (
                                    reporter_email,
                                    reported_email,
                                    food_post_id
                                )
                                VALUES (?, ?, ?)
                                """,
                                (
                                    ngo_email,
                                    assigned_volunteer,
                                    post_id
                                )
                            )

                            execute_query(
                                """
                                UPDATE users
                                SET reports_count = reports_count + 1
                                WHERE email = ?
                                """,
                                (assigned_volunteer,)
                            )

                            add_notification(
                                ADMIN_EMAIL,
                                f"Volunteer {assigned_volunteer} "
                                f"was reported by NGO "
                                f"{ngo_email} for Post #{post_id}."
                            )

                            st.success(
                                "Volunteer reported successfully."
                            )

                            st.rerun()

    # ==========================================
    # TAB 2: NOTIFICATIONS
    # ==========================================
    with tabs[1]:
        rows = execute_query(
            """
            SELECT message, timestamp
            FROM notifications
            WHERE recipient_email = ?
            ORDER BY id DESC
            """,
            (ngo_email,),
            fetch=True
        )

        if rows:
            for message, timestamp in rows:
                st.info(f"{timestamp}\n\n{message}")
        else:
            st.info("No notifications.")

    # ==========================================
    # TAB 3: SUPPORT
    # ==========================================
    with tabs[2]:
        contact_support()

def energy_dashboard():
    st.title("♻️ Waste-to-Energy Dashboard")

    partner_email = st.session_state.user["email"]

    tabs = st.tabs([
        "Spoiled Food Requests",
        "Notifications",
        "Support"
    ])

    # ==========================================
    # TAB 1: SPOILED FOOD REQUESTS
    # ==========================================
    with tabs[0]:
        rows = execute_query(
            """
            SELECT
                id,
                donor_email,
                food_type,
                meals,
                quantity,
                pickup_location,
                notes,
                status,
                assigned_energy_partner,
                processing_method,
                assigned_volunteer
            FROM food_posts
            WHERE status = 'Spoiled'
            AND (
                assigned_energy_partner IS NULL
                OR assigned_energy_partner = ?
            )       
            ORDER BY id DESC
            """,
            (partner_email,),
            fetch=True
        )

        if not rows:
            st.info("No spoiled food requests available.")
        else:
            for row in rows:
                (
                    post_id,
                    donor_email,
                    food_type,
                    meals,
                    quantity,
                    pickup_location,
                    notes,
                    status,
                    assigned_energy_partner,
                    processing_method,
                    assigned_volunteer
                ) = row

                with st.expander(
                    f"Post #{post_id} - {food_type} ({meals} meals)"
                ):
                    st.write(f"**Donor Email:** {donor_email}")
                    st.write(f"**Food Type:** {food_type}")
                    st.write(f"**Meals:** {meals}")
                    st.write(f"**Quantity:** {quantity}")
                    st.write(f"**Pickup Location:** {pickup_location}")
                    st.write(f"**Notes:** {notes or '-'}")
                    st.write(f"**Status:** {status}")

                    st.write(
                        f"**Assigned Partner:** "
                        f"{assigned_energy_partner if assigned_energy_partner else 'Not Assigned'}"
                    )

                    st.write(
                        f"**Assigned Volunteer:** "
                        f"{assigned_volunteer if assigned_volunteer else 'Not Assigned'}"
                    )

                    # Accept Button
                    if st.button(
                        "✅ Accept",
                        key=f"energy_accept_{post_id}"
                    ):

                        current_partner = execute_query(
                            """
                            SELECT assigned_energy_partner
                            FROM food_posts
                            WHERE id = ?
                            """,
                            (post_id,),
                            fetchone=True
                        )

                        if not current_partner[0]:

                            execute_query(
                                """
                                UPDATE food_posts
                                SET assigned_energy_partner = ?
                                WHERE id = ?
                                """,
                                (partner_email, post_id)
                            )

                            st.success("Request accepted successfully.")

                        else:
                            st.warning(
                                "Already accepted by another partner."
                            )

                        st.rerun()
                        

                    # Processing Method Selection
                    method = st.selectbox(
                        "Processing Method",
                        PROCESSING_METHODS,
                        index=(
                            PROCESSING_METHODS.index(processing_method)
                            if processing_method in PROCESSING_METHODS
                            else 0
                        ),
                        key=f"energy_method_{post_id}"
                    )

                    # Mark Processed Button
                    if not assigned_energy_partner:

                        st.warning(
                            "Please accept this request first."
                        )

                    elif assigned_energy_partner != partner_email:

                        st.warning(
                            "Only assigned partner can process this food."
                        )

                    elif st.button(
                        "♻️ Mark Processed",
                        key=f"energy_process_{post_id}"
                    ):
                        # Update food_posts
                        execute_query(
                            """
                            UPDATE food_posts
                            SET status = 'Processed',
                                processing_method = ?,
                                assigned_energy_partner = ?
                            WHERE id = ?
                            """,
                            (
                                method,
                                partner_email,
                                post_id
                            )
                        )

                        # Insert into energy_requests
                        execute_query(
                            """
                            INSERT INTO energy_requests
                            (
                                food_post_id,
                                partner_email,
                                processing_method
                            )
                            VALUES (?, ?, ?)
                            """,
                            (
                                post_id,
                                partner_email,
                                method
                            )
                        )

                        # Add tracking log
                        add_tracking_log(
                            post_id,
                            "Processed",
                            partner_email,
                            f"Processed using {method}"
                        )

                        # Notify admin
                        add_notification(
                            ADMIN_EMAIL,
                            f"Food Post #{post_id} was processed "
                            f"using {method} by {partner_email}."
                        )

                        st.success(
                            f"Post processed successfully using {method}."
                        )
                        st.rerun()
                        
                    # Report Volunteer
                    already_reported = execute_query(
                        """
                        SELECT 1
                        FROM reports
                        WHERE reporter_email = ?
                        AND reported_email = ?
                        AND food_post_id = ?
                        """,
                        (
                            partner_email,
                            assigned_volunteer,
                            post_id
                        ),
                        fetch=True
                    )                    
                    if st.button(
                        "🚨 Report Volunteer",
                        key=f"energy_report_{post_id}"
                    ):
                        if already_reported:

                            st.warning(
                                "You have already reported this volunteer."
                            )

                        else:
                            execute_query(
                                """
                                INSERT INTO reports
                                (
                                    reporter_email,
                                    reported_email,
                                    food_post_id
                                )
                                VALUES (?, ?, ?)
                                """,
                                (
                                    partner_email,
                                    assigned_volunteer,
                                    post_id
                                )
                            )                            
                            execute_query(
                                """
                                UPDATE users
                                SET reports_count = reports_count + 1
                                WHERE email = ?
                                """,
                                (assigned_volunteer,)
                            )

                            add_notification(
                                ADMIN_EMAIL,
                                f"Volunteer {assigned_volunteer} "
                                f"was reported by Waste-to-Energy Partner "
                                f"{partner_email} for Post #{post_id}."
                            )

                            st.success(
                                "Volunteer reported successfully."
                            )

                            st.rerun()  

    # ==========================================
    # TAB 2: NOTIFICATIONS
    # ==========================================
    with tabs[1]:
        rows = execute_query(
            """
            SELECT message, timestamp
            FROM notifications
            WHERE recipient_email = ?
            ORDER BY id DESC
            """,
            (partner_email,),
            fetch=True
        )

        if rows:
            for message, timestamp in rows:
                st.info(f"{timestamp}\n\n{message}")
        else:
            st.info("No notifications.")

    # ==========================================
    # TAB 3: SUPPORT
    # ==========================================
    with tabs[2]:
        contact_support()
# ==========================================
# ADMIN + ROUTER
# ==========================================
def admin_dashboard():
    st.title("🛠️ Admin Dashboard")

    tabs = st.tabs([
        "Overview",
        "Users",
        "Food Posts",
        "Notifications",
        "Tracking Logs",
        "Impact Dashboard",
        "Support"
    ])

    # ==========================================
    # TAB 1: OVERVIEW
    # ==========================================
    with tabs[0]:
        filter_option = st.selectbox(
            "📅 Filter Overview By",
            [
                "All",
                "Today",
                "Last 7 Days",
                "Last 30 Days",
                "Custom"
            ]
        )

        if filter_option == "Custom":
            col1, col2 = st.columns(2)

            with col1:
                start_date = st.date_input(
                    "From Date"
                )

            with col2:
                end_date = st.date_input(
                    "To Date"
                )

        date_condition = ""
        params = ()

        if filter_option == "Today":
            date_condition = (
                "WHERE DATE(created_at) = DATE('now', 'localtime')"
            )

        elif filter_option == "Last 7 Days":
            date_condition = (
                "WHERE DATE(created_at) >= DATE('now', '-6 days')"
            )

        elif filter_option == "Last 30 Days":
            date_condition = (
                "WHERE DATE(created_at) >= DATE('now', '-29 days')"
            )

        elif filter_option == "Custom":
            date_condition = (
                "WHERE DATE(created_at) BETWEEN ? AND ?"
            )

            params = (
                str(start_date),
                str(end_date)
            )                

        total_users = execute_query(
            "SELECT COUNT(*) FROM users",
            fetchone=True
        )[0]

        total_posts = execute_query(
            f"""
            SELECT COUNT(*)
            FROM food_posts
            {date_condition}
            """,
            params,
            fetchone=True
        )[0]

        total_meals = execute_query(
            f"""
            SELECT COALESCE(SUM(meals),0)
            FROM food_posts
            {date_condition}
            """,
            params,
            fetchone=True
        )[0]

        delivered = execute_query(
            f"""
            SELECT COUNT(*)
            FROM food_posts
            WHERE status='Delivered'
            {'AND DATE(created_at) = DATE("now","localtime")' if filter_option=="Today" else ''}
            """,
            fetchone=True
        )[0]

        spoiled = execute_query(
            "SELECT COUNT(*) FROM food_posts WHERE status='Spoiled'",
            fetchone=True
        )[0]

        processed = execute_query(
            "SELECT COUNT(*) FROM food_posts WHERE status='Processed'",
            fetchone=True
        )[0]

        cols = st.columns(6)

        metrics = [
            ("Users", total_users),
            ("Posts", total_posts),
            ("Meals", total_meals),
            ("Delivered", delivered),
            ("Spoiled", spoiled),
            ("Processed", processed)
        ]

        for col, (label, value) in zip(cols, metrics):
            col.metric(label, value)

    # ==========================================
    # TAB 2: USERS
    # ==========================================
    with tabs[1]:
        st.subheader("👥 User Management")

        users = execute_query(
            """
            SELECT
            id,
            name,
            email,
            location,
            contact1,
            contact2,
            role,
    reports_count,
    is_blocked
            FROM users
            ORDER BY id DESC
            """,
            fetch=True
        )

        if not users:
            st.info("No users found.")
        else:
            df = pd.DataFrame(
                users,
                columns=[
                   "ID",
                   "Name",
                   "Email",
                   "Location",
                   "Contact1",
                   "Contact2",
                   "Role",
                   "Reports",
                   "Blocked"
                ]
            )

            # -------------------------------
            # Filters
            # -------------------------------
            col1, col2, col3 = st.columns(3)

            search_text = col1.text_input(
                "🔍 Search by Name or Email"
            )

            role_options = ["All"] + sorted(
                df["Role"].dropna().unique().tolist()
            )
            selected_role = col2.selectbox(
                "🎭 Filter by Role",
                role_options
            )

            location_options = ["All"] + sorted(
                [
                    loc for loc in df["Location"]
                    .fillna("")
                    .astype(str)
                    .unique()
                    .tolist()
                    if loc.strip()
                ]
            )
            selected_location = col3.selectbox(
                "📍 Filter by Location",
                location_options
            )

            # -------------------------------
            # Apply Search Filter
            # -------------------------------
            if search_text:
                search_lower = search_text.lower()
                df = df[
                    df["Name"].astype(str)
                    .str.lower()
                    .str.contains(search_lower, na=False)
                    |
                    df["Email"].astype(str)
                    .str.lower()
                    .str.contains(search_lower, na=False)
                ]

            # -------------------------------
            # Apply Role Filter
            # -------------------------------
            if selected_role != "All":
                df = df[df["Role"] == selected_role]

            # -------------------------------
            # Apply Location Filter
            # -------------------------------
            if selected_location != "All":
                df = df[df["Location"] == selected_location]

            st.caption(f"Showing {len(df)} user(s).")

            if df.empty:
                st.warning("No users match the selected filters.")
            else:
                # -------------------------------
                # Expandable User Cards
                # -------------------------------
                for _, row in df.iterrows():
                    title = (
                        f"{role_icon(row['Role'])} "
                        f"{row['Name']} "
                        f"({row['Role']})"
                    )

                    with st.expander(title):
                        c1, c2 = st.columns(2)

                        with c1:
                            st.write(f"**ID:** {row['ID']}")
                            st.write(f"**Name:** {row['Name']}")
                            st.write(f"**Email:** {row['Email']}")
                            st.write(f"**Role:** {row['Role']}")
                            st.write(f"**Reports:** {row['Reports']}")
                            st.write(
                                f"**Blocked:** {'Yes' if row['Blocked'] == 1 else 'No'}"
                            )
                            if row["Reports"] >= 3:
                                st.error(
                                    "⚠️ This user has high reports count."
                                )
                        with c2:
                            st.write(
                                f"**Location:** "
                                f"{row['Location'] or '-'}"
                            )
                            st.write(
                                f"**Contact 1:** "
                                f"{row['Contact1'] or '-'}"
                            )
                            st.write(
                                f"**Contact 2:** "
                                f"{row['Contact2'] or '-'}"
                            )

                        st.markdown("---")
                        col_block, col_unblock = st.columns(2)
                    if row["Email"] == ADMIN_EMAIL:
                        st.info("Admin account protected.")

                    else:
                        # Block User
                        if col_block.button(
                            "🚫 Block",
                            key=f"block_{row['ID']}"
                        ):

                            execute_query(
                                """
                                UPDATE users
                                SET is_blocked = 1
                                WHERE id = ?
                                """,
                                (row["ID"],)
                            )

                            st.success("User blocked successfully.")
                            st.rerun()

                        # Unblock User
                        if col_unblock.button(
                            "✅ Unblock",
                            key=f"unblock_{row['ID']}"
                        ):

                            execute_query(
                                """
                                UPDATE users
                                SET is_blocked = 0
                                WHERE id = ?
                                """,
                                (row["ID"],)
                            )

                            st.success("User unblocked successfully.")
                            st.rerun()

                        

    # ==========================================
    # TAB 3: FOOD POSTS
    # ==========================================
    with tabs[2]:

        filter_option = st.selectbox(
            "📅 Filter Food Posts By",
            [
                "All",
                "Today",
                "Last 7 Days",
                "Last 30 Days"
            ],
            key="food_posts_filter"
        )

        status_filter = st.selectbox(
            "📌 Filter By Status",
            [
                "All",
                "Uploaded",
                "Assigned",
                "Picked Up",
                "Delivered",
                "Spoiled",
                "Processed"
            ],
            key="status_filter"
        )

        query = "SELECT * FROM food_posts"
        conditions = []

        if filter_option == "Today":
            conditions.append(
                "DATE(created_at)=DATE('now','localtime')"
            )

        elif filter_option == "Last 7 Days":
            conditions.append(
                "DATE(created_at)>=DATE('now','-6 days')"
            )

        elif filter_option == "Last 30 Days":
            conditions.append(
                "DATE(created_at)>=DATE('now','-29 days')"
            )

        if status_filter != "All":
            conditions.append(
                f"status='{status_filter}'"
            )

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC"

        df = pd.read_sql_query(
            query,
            conn
        )

        st.dataframe(
            df,
            use_container_width=True
        )

    # ==========================================
    # TAB 4: NOTIFICATIONS
    # ==========================================
    with tabs[3]:
        df = pd.read_sql_query(
            "SELECT * FROM notifications ORDER BY id DESC",
            conn
        )
        st.dataframe(df, use_container_width=True)

    # ==========================================
    # TAB 5: TRACKING LOGS
    # ==========================================
    with tabs[4]:
        df = pd.read_sql_query(
            "SELECT * FROM tracking_logs ORDER BY id DESC",
            conn
        )
        st.dataframe(df, use_container_width=True)

    # ==========================================
    # TAB 6: IMPACT DASHBOARD
    # ==========================================
    with tabs[5]:
        total_meals_saved = execute_query(
            "SELECT COALESCE(SUM(meals), 0) FROM food_posts",
            fetchone=True
        )[0]

        people_helped = execute_query(
            """
            SELECT COALESCE(SUM(meals), 0)
            FROM food_posts
            WHERE status='Delivered'
            """,
            fetchone=True
        )[0]

        food_waste_reduced = total_meals_saved

        food_converted_to_energy = execute_query(
            """
            SELECT COUNT(*)
            FROM food_posts
            WHERE status='Processed'
            """,
            fetchone=True
        )[0]

        active_volunteers = execute_query(
            """
            SELECT COUNT(*)
            FROM users
            WHERE role='Volunteer'
            """,
            fetchone=True
        )[0]

        ngos_participating = execute_query(
            """
            SELECT COUNT(*)
            FROM users
            WHERE role='NGO / Trust'
            """,
            fetchone=True
        )[0]

        metrics = [
            ("Total Meals Saved", total_meals_saved),
            ("People Helped", people_helped),
            ("Food Waste Reduced", food_waste_reduced),
            ("Food Converted to Energy", food_converted_to_energy),
            ("Active Volunteers", active_volunteers),
            ("NGOs Participating", ngos_participating)
        ]

        cols = st.columns(3)

        for i, (label, value) in enumerate(metrics):
            cols[i % 3].metric(label, value)

    # ==========================================
    # TAB 7: SUPPORT
    # ==========================================
    with tabs[6]:
        contact_support()


def render_top_navigation():
    """Top navigation bar shown after login."""
    user = st.session_state.user

    unread_count = get_unread_notification_count(user["email"])

    # User information
    st.markdown(
        f"""
        ### 👤 {user['name']} ({user['role']})
        🔔 Unread Notifications: {unread_count}
        """
    )

    # Navigation buttons
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    if st.session_state.user["role"] == "Admin":

        col1, col2, col3, col4, col5 = st.columns(5)

        if col1.button("🏠 Dashboard", use_container_width=True):
            go_to("dashboard")

        if col2.button("✏️ Edit Profile", use_container_width=True):
            go_to("edit_profile")

        if col3.button("🔔 Notifications", use_container_width=True):
            go_to("notifications")

        if col4.button("📞 Contact & Support", use_container_width=True):
            go_to("support")

        if col5.button("🚪 Logout", use_container_width=True):
            logout()

    else:

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        if col1.button("🏠 Dashboard", use_container_width=True):
            go_to("dashboard")

        if col2.button("✏️ Edit Profile", use_container_width=True):
            go_to("edit_profile")

        if col3.button("📝 Report Issue", use_container_width=True):
            go_to("report_issue")

        if col4.button("🔔 Notifications", use_container_width=True):
            go_to("notifications")

        if col5.button("📞 Contact & Support", use_container_width=True):
            go_to("support")

        if col6.button("🚪 Logout", use_container_width=True):
            logout()

    st.markdown("---")

def render_current_page():
    page = st.session_state.current_page
    role = st.session_state.user["role"]

    if page == "edit_profile":
        edit_profile()
        return

    if page == "report_issue":
        report_issue()
        return

    if page == "notifications":
        notifications_page()
        return

    if page == "contact_support":
        contact_support()
        return

    if role == "Admin":
        admin_dashboard()
    elif role == "Donor":
        donor_dashboard()
    elif role == "Volunteer":
        volunteer_dashboard()
    elif role == "NGO / Trust":
        ngo_dashboard()
    elif role == "Waste-to-Energy Partner":
        energy_dashboard()
# ==========================================
# MAIN
# ==========================================
def main():
    load_theme()
    create_tables()
    create_admin()
    init_session()
    

    if not st.session_state.logged_in:
        login_page()
        return

    render_top_navigation()
    render_current_page()


if __name__ == "__main__":
    main()
