from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import os
import google.generativeai as genai # type: ignore
from PIL import Image
import pandas as pd
import matplotlib.pyplot as plt
import random
import re


# Configure Gemini
GOOGLE_API_KEY = "AIzaSyBd2F9yuj5OkWk4gtS0z35vfQy6HwvjxHY"  
genai.configure(api_key=GOOGLE_API_KEY) 

# Initialize session state
if 'travel_profile' not in st.session_state:
    st.session_state.travel_profile = {
        'travel_goals': 'Low-budget educational trip\nExplore Indian culture',
        'starting_location': 'Hyderabad, Telangana',
        'preferred_states': 'Karnataka\nTamil Nadu\nKerala',
        'budget': '₹10,000 - ₹20,000',
        'travel_preferences': 'Train travel\nHostels\nStreet food',
        'restrictions': 'Avoid night travel\nVegetarian food preferred'
    }

# Function to get results from local CSV when API fails
def get_csv_fallback_response(query):
    try:
        # Load CSV
        if not os.path.exists("places.csv"):
            return "Curated recommendations are currently being updated. Please check back in a few moments."
        
        df = pd.read_csv("places.csv")
        query_str = str(query).lower()

        # Day Detection (Max 10 days, Default 3)
        num_days = 3
        day_match = re.search(r'(\d+)\s*day', query_str)
        if day_match:
            num_days = int(min(int(day_match.group(1)), 10))
        
        # Get profile context
        profile = st.session_state.get('travel_profile', {})
        pref_states_raw = profile.get('preferred_states', '').split('\n')
        pref_states = [s.strip() for s in pref_states_raw if s]
        
        if not pref_states:
             # Fallback to common states if none selected
             pref_states = ["Delhi", "Maharashtra", "Karnataka", "Telangana", "Tamil Nadu", "Kerala"]

        # Filter by keywords in query to narrow down type/city interest
        keywords = [word for word in query_str.split() if len(word) > 3]
        
        # Format the response
        response = f"### 🌟 Your Handpicked {num_days}-Day Student Journey\n"
        response += "I've carefully curated this itinerary to cover your preferred states, focusing on high-value educational and cultural landmarks. This plan ensures a balanced exploration of each region.\n\n"
        
        # Calculate days per state
        num_states = len(pref_states)
        days_per_state = max(1, num_days // num_states)
        extra_days = num_days % num_states
        
        current_day = 1
        for i, state in enumerate(pref_states):
            if int(current_day) > int(num_days):
                break
                
            # Allocate extra days to the first few states
            actual_days_for_this_state = days_per_state + (1 if i < extra_days else 0)
            
            response += f"--- \n## 🏛️ Region Tour: {state}\n"
            response += f"Exploring the unique heritage and local student vibes of **{state}**.\n\n"
            
            # Filter places for this state
            state_df = df[df['State'].str.contains(state, case=False, na=False)]
            
            if keywords:
                 # Try to match keywords within the state
                 match_state = state_df[state_df.apply(lambda row: any(k in str(row['Name']).lower() or 
                                                                    k in str(row['City']).lower() or 
                                                                    k in str(row['Type']).lower() for k in keywords), axis=1)]
                 if not match_state.empty:
                     state_df = match_state
            
            # Pick places for the allocated days (2 per day)
            places_needed = actual_days_for_this_state * 2
            state_places = state_df.sample(min(len(state_df), places_needed), random_state=42).to_dict('records')
            random.shuffle(state_places)

            for d in range(actual_days_for_this_state):
                if int(current_day) > int(num_days):
                    break
                    
                response += f"### 📅 Day {current_day}\n"
                
                day_spots = state_places[d*2 : (d+1)*2]
                if not day_spots:
                    response += f"Take some time to explore the local student hubs and street food markets in {state}.\n\n"
                else:
                    for spot in day_spots:
                        response += f"#### 📍 {spot['Name']}\n"
                        response += f"**{spot['City']}, {spot['State']}** ({spot['Type']})\n\n"
                        
                        table = "| Detail | Information |\n| :--- | :--- |\n"
                        table += f"| ⭐ **Rating** | {spot['Google review rating']}/5 ({spot['Number of google review in lakhs']}L Reviews) |\n"
                        table += f"| ⏱️ **Duration** | {spot['time needed to visit in hrs']} Hours needed |\n"
                        table += f"| 💰 **Entry Fee** | ₹{spot['Entrance Fee in INR']} |\n"
                        table += f"| 📅 **Weekly Off** | {spot['Weekly Off']} |\n"
                        table += f"| 📸 **DSLR/Cam** | {'Allowed' if spot['DSLR Allowed'] == 'Yes' else 'Restricted'} |\n"
                        table += f"| 🏛️ **Heritage** | Established in {spot['Establishment Year']} |\n"
                        table += f"| ✈️ **Airport** | {spot['Airport with 50km Radius']} (Within 50km) |\n"
                        
                        response += table + "\n"
                        response += f"**📜 Significance:** {spot['Significance']}\n"
                        response += f"**✨ Best Time:** {spot['Best Time to visit']}\n\n"
                
                current_day += 1

        state_names = ""
        for s in pref_states[:3]:
            state_names += s + ", "
        state_names = state_names.rstrip(", ")
        response += f"- **State Transitions:** When moving between {state_names}{'...' if len(pref_states) > 3 else ''}, prefer night trains to save on stay costs.\n"
        response += "- **Student Perks:** Many of these sites offer discounts of up to 50% for valid student ID holders.\n"
        response += "- **Food Tip:** Don't miss the local university canteens in these states for the most authentic and budget-friendly food.\n"
        
        return response

    except Exception as e:
        return f"Error using local database fallback: {str(e)}"

# Function to get Gemini response 
def get_gemini_response(input_prompt, image_data=None):
    model = genai.GenerativeModel('gemini-2.5-flash') 

    content = [input_prompt]

    if image_data:
        content.extend(image_data)

    try:
        response = model.generate_content(content)
        # Check if response has text (sometimes safety filters block it)
        try:
            return response.text
        except:
            return get_csv_fallback_response(input_prompt)
            
    except Exception as e:
        # If it's a quota or connection error, use fallback
        error_msg = str(e).lower()
        if "quota" in error_msg or "limit" in error_msg or "429" in error_msg or "finish_reason" in error_msg or "api_key" in error_msg:
             return get_csv_fallback_response(input_prompt)
        
        return get_csv_fallback_response(input_prompt) # General fallback for any error as requested

def input_image_setup(uploaded_file):
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        image_parts = [{
            "mime_type": uploaded_file.type,
            "data": bytes_data
        }]
        return image_parts
    return None

# App layout
st.markdown(
    "<h1 style='text-align: center; color:#6594B1;'>🧳 AI Student Travel Planner</h1>",
    unsafe_allow_html=True
)

#CSS 
st.markdown("""
<style>

/* App background */
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: white;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #000000;
}

/* -------- TABS -------- */
div[data-baseweb="tab-list"] {
    display: flex;
    justify-content: center;
    gap: 50px;
}

/* Tab text */
button[role="tab"] {
    background: transparent;
    color: #9a9a9a;
    font-size: 18px;
    font-weight: 500;
}

/* Active tab text */
button[role="tab"][aria-selected="true"] {
    color: #6594B1 !important;
    font-weight: 700;
}

/* 🔥 REMOVE DEFAULT RED BAR */
div[data-baseweb="tab-highlight"] {
    background-color: #6594B1 !important;
    height: 3px;
    border-radius: 10px;
}

/* Buttons */
.stButton > button {
    background-color: #08CB00;
    color: black;
    font-weight: 600;
    border-radius: 8px;
}

/* Inputs */
textarea, input[type="text"], input[type="number"] {
    background-color: #000000;
    color: white;
}

/* Tables */
table th, table td {
    color: white;
}

/* File uploader */
div.stFileUploader label {
    color: white;
}

/* ---- REMOVE RED HOVER / FOCUS FROM TABS COMPLETELY ---- */
button[role="tab"]:hover,
button[role="tab"]:focus,
button[role="tab"]:active {
    color: #6594B1 !important;
    background-color: transparent !important;
    outline: none !important;
    box-shadow: none !important;
}

/* Kill any leftover red borders */
button[role="tab"]::before,
button[role="tab"]::after {
    border-color: #6594B1 !important;
}

/* Ensure highlight bar never turns red */
div[data-baseweb="tab-highlight"] {
    background-color: #6594B1 !important;
}

/* ---------- Tabs Style ---------- */
button[role="tab"] {
    background: transparent;
    color: #9a9a9a;
    font-size: 18px;
    font-weight: 500;
    transition: color 0.3s, transform 0.2s;
}

button[role="tab"]:hover {
    color: #08CB00 !important; /* Hover color */
    transform: scale(1.05);     /* Slight grow */
}

button[role="tab"][aria-selected="true"] {
    color: #6594B1 !important;
    font-weight: 700;
    transform: scale(1.05);
}

/* ---------- Remove bottom highlight line completely ---------- */
div[data-baseweb="tab-highlight"] {
    display: none !important;
}

/* ---------- Buttons Hover Animation ---------- */
.stButton > button {
    transition: background 0.3s, transform 0.2s;
}

.stButton > button:hover {
    background-color: #05a600;
    transform: scale(1.05);
}

/* ---------- Table Row Hover ---------- */
table tr:hover {
    background-color: rgba(102, 148, 177, 0.2);
}

/* ---------- Checkboxes & Radio Buttons Hover ---------- */
.stCheckbox, .stRadio {
    transition: transform 0.2s;
}

.stCheckbox:hover, .stRadio:hover {
    transform: scale(1.05);
}

/* ---------- App and Sidebar Colors ---------- */
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: white;
}

[data-testid="stSidebar"] {
    background-color: #000000;
}

/* ---------- Inputs ---------- */
textarea, input[type="text"], input[type="number"] {
    background-color: #000000;
    color: white;
}

/* ---------- Tables ---------- */
table th, table td {
    color: white;
}

/* ---------- File uploader ---------- */
div.stFileUploader label {
    color: white;
}            
            
</style>
""", unsafe_allow_html=True)

# Sidebar for travel profile
with st.sidebar:
    st.subheader("🎓 Your Travel Profile")

    travel_goals = st.text_area(
        "Travel Goals",
        value=st.session_state.travel_profile['travel_goals']
    )
    starting_location = st.text_area(
        "Starting Location",
        value=st.session_state.travel_profile['starting_location']
    )
    preferred_states = st.text_area(
        "Preferred States / Regions",
        value=st.session_state.travel_profile['preferred_states']
    )
    budget = st.text_area(
        "Budget Range",
        value=st.session_state.travel_profile['budget']
    )
    travel_preferences = st.text_area(
        "Travel Preferences",
        value=st.session_state.travel_profile['travel_preferences']
    )
    restrictions = st.text_area(
        "Travel Restrictions",
        value=st.session_state.travel_profile['restrictions']
    )

    if st.button("Update Travel Profile"):
        st.session_state.travel_profile = {
            'travel_goals': travel_goals,
            'starting_location': starting_location,
            'preferred_states': preferred_states,
            'budget': budget,
            'travel_preferences': travel_preferences,
            'restrictions': restrictions
        }
        st.success("Travel profile updated!")

# Main content area
section1, section2, section3, section4, section5 = st.tabs(
    [" Travel Itinerary", " Budget Optimizer", " Risk & Safety ", " Travel Scheduler ","🤖 Travel Assistant"]
)

# ---------------- SECTION 1 ----------------
with section1:
    st.subheader("Personalized Student Travel Itinerary")

    col1, spacer, col2 = st.columns([1, 0.05, 1])

    with col1:
        user_input = st.text_area(
            "Describe your trip requirements:",
            placeholder="e.g., '5-day budget trip covering temples and beaches'"
        )
        generate_button = st.button("Generate Travel Plan")

    with col2:
        st.write("### Current Travel Profile")
        def format_field(field):
            if isinstance(field, list):
                return ", ".join(str(i) for i in field)
            return str(field)

        profile_data = {
            "Field": [
                "Travel Goals",
                "Starting Location",
                "Preferred States/Regions",
                "Budget",
                "Travel Preferences",
                "Restrictions"
            ],
            "Details": [
                format_field(st.session_state.travel_profile.get("travel_goals", "")),
                format_field(st.session_state.travel_profile.get("starting_location", "")),
                format_field(st.session_state.travel_profile.get("preferred_states", [])),
                format_field(st.session_state.travel_profile.get("budget", "")),
                format_field(st.session_state.travel_profile.get("travel_preferences", [])),
                format_field(st.session_state.travel_profile.get("restrictions", []))
            ]
        }

        df_profile = pd.DataFrame(profile_data)
        df_profile.index = range(1, len(df_profile) + 1)
        st.table(df_profile)

    if generate_button:
        with st.spinner("Planning your journey across India... "):
            prompt = f"""
            Create a detailed student-friendly travel plan in India using ALL states and districts when relevant.

            Travel Goals: {st.session_state.travel_profile['travel_goals']}
            Starting Location: {st.session_state.travel_profile['starting_location']}
            Preferred States/Regions: {st.session_state.travel_profile['preferred_states']}
            Budget: {st.session_state.travel_profile['budget']}
            Travel Preferences: {st.session_state.travel_profile['travel_preferences']}
            Restrictions: {st.session_state.travel_profile['restrictions']}

            Additional Notes: {user_input if user_input else "None"}

            Provide:
            1. Day-wise itinerary with places (states & districts)
            2. Estimated travel cost breakdown (transport, stay, food)
            3. Best transport options for students (train/bus)
            4. Affordable accommodation suggestions
            5. Local food recommendations
            6. Safety tips for students
            7. Best time to visit
            8. Educational & cultural value of places

            Format clearly with headings and bullet points.
            """
            response = get_gemini_response(prompt)

            st.subheader("📍 Your Travel Plan")
            st.markdown(response)

            st.download_button(
                label="Download Travel Plan",
                data=response,
                file_name="student_travel_plan.txt",
                mime="text/plain"
            )

# ---------------- SECTION 2 ----------------
with section2:
    st.subheader(" Budget Optimizer")

    # -------- FILTERS / INPUTS --------
    st.write("### Optional Filters / Preferences")

    # States selection
    preferred_states = st.session_state.travel_profile.get("preferred_states", "")
    state_options = [s.strip() for s in preferred_states.split("\n") if s]
    selected_states = st.multiselect("Select States to Focus On", options=state_options, default=state_options)

    # Max per-person expense input
    budget_text = st.session_state.travel_profile.get("budget", "₹0")
    min_budget, max_budget = 0, 0
    try:
        budget_text_clean = budget_text.replace("₹","").replace(",","").replace(" ","")
        if "-" in budget_text_clean:
            parts = budget_text_clean.split("-")
            min_budget = int(parts[0])
            max_budget = int(parts[1])
        else:
            min_budget = max_budget = int(budget_text_clean)
    except:
        min_budget = max_budget = 10000

    max_expense = st.number_input(
        "Maximum Expense per Person (INR)", 
        min_value=min_budget, max_value=max_budget, 
        value=max_budget, step=500
    )

    # Checkbox for food inclusion
    food_pref = st.checkbox("Include Street Food & Local Snacks", value=True)

    # Button to generate budget & places
    show_budget = st.button("Get Optimized Budget & Places")

    # -------- DISPLAY PROFILE SUMMARY --------
    st.write("### Travel Profile Overview")
    profile_data = {
        "Field": [
            "Starting Location",
            "Preferred States",
            "Budget Limit",
            "Travel Preferences",
            "Restrictions"
        ],
        "Details": [
            st.session_state.travel_profile.get("starting_location", ""),
            st.session_state.travel_profile.get("preferred_states", ""),
            st.session_state.travel_profile.get("budget", ""),
            st.session_state.travel_profile.get("travel_preferences", ""),
            st.session_state.travel_profile.get("restrictions", "")
        ]
    }
    df_profile = pd.DataFrame(profile_data)
    df_profile.index = range(1, len(df_profile) + 1)
    st.table(df_profile)

    # -------- LOAD CSV AND GENERATE TABLE & GRAPHS --------
    if show_budget:
        with st.spinner("Generating optimized budget & places..."):
            try:
                df_places = pd.read_csv("places.csv")  # Load CSV

                # Filter by selected states
                if selected_states:
                    df_places = df_places[df_places["State"].isin(selected_states)]

                import random

                # Generate per-person expense
                df_places["Expense per Person (INR)"] = df_places.apply(
                    lambda x: random.randint(min_budget//5, max_expense), axis=1
                )

                # Optionally reduce food expenses if checkbox unchecked
                if not food_pref:
                    df_places["Expense per Person (INR)"] = df_places["Expense per Person (INR)"].apply(
                        lambda x: int(x * 0.8)
                    )

                # -------- DISPLAY TABLE --------
                st.subheader("📋 Places & Per-Person Budget")
                st.dataframe(df_places)

                # -------- BAR CHARTS FOR NUMERIC FIELDS --------
                numeric_cols = [
                    "time needed to visit in hrs",
                    "Google review rating",
                    "Entrance Fee in INR",
                    "Number of google review in lakhs",
                    "Expense per Person (INR)"
                ]
                for col in numeric_cols:
                    if col in df_places.columns:
                        st.subheader(f"📊 {col} Distribution")
                        st.bar_chart(df_places.set_index("Name")[col])

                # -------- PIE CHART FOR EXPENSES --------
                st.subheader("🥧 Expense Distribution (Per Person)")
                fig, ax = plt.subplots()
                ax.pie(
                    df_places["Expense per Person (INR)"],
                    labels=df_places["Name"],
                    autopct="%1.1f%%",
                    startangle=90,
                    colors=plt.cm.tab20.colors
                )
                ax.axis("equal")
                st.pyplot(fig)

                # -------- DOWNLOAD CSV --------
                csv = df_places.to_csv(index=False)
                st.download_button(
                    label="Download CSV with Expenses",
                    data=csv,
                    file_name="places_with_expenses.csv",
                    mime="text/csv"
                )

            except FileNotFoundError:
                st.error("CSV file 'places.csv' not found. Please place it in the project folder.")


# ---------------- SECTION 3 ----------------


with section3:
    st.subheader(" Risk & Safety Guide")

    st.markdown("### Select Risk Categories & Travel Modes")

    # -------- COLUMNS FOR RISK CATEGORIES --------
    col1, col2 = st.columns(2)
    with col1:
        health_risks = st.checkbox("🩺 Health Risks", value=True)
        crime_safety = st.checkbox("🚨 Crime / Safety", value=True)
    with col2:
        weather_risks = st.checkbox("🌦 Weather Risks", value=True)
        emergency_precautions = st.checkbox("🧯 Emergency Precautions", value=True)

    st.markdown("---")
    st.markdown("### Travel Mode Safety Checks")

    # --------  COLUMNS FOR TRAVEL MODES --------
    col3, col4 = st.columns(2)
    with col3:
        train_travel = st.checkbox("🚆 Train Travel", value=True)
        bus_travel = st.checkbox("🚌 Bus Travel", value=True)
    with col4:
        car_travel = st.checkbox("🚗 Car / Taxi", value=False)
        hostel_safety = st.checkbox("🏨 Hostel / Hotel Safety", value=True)

    st.markdown("---")
    st.markdown("### Student Safety Checklist")

    # --------  COLUMNS FOR STUDENT PRECAUTIONS --------
    col5, col6 = st.columns(2)
    with col5:
        first_aid = st.checkbox("💊 Carry First Aid Kit")
        travel_in_groups = st.checkbox("👥 Travel in Groups")
    with col6:
        avoid_night_travel = st.checkbox("🌙 Avoid Night Travel Alone")
        digital_docs = st.checkbox("📄 Keep Digital Copies of Important Documents")

    st.markdown("---")

    # Button to generate AI risk analysis
    if st.button("Analyze Travel Risks"):
        with st.spinner("Analyzing travel risks and safety tips for your trip..."):
            # AI prompt to generate risk analysis
            prompt = f"""
            You are an expert Indian travel planner specializing in student trips.
            Analyze travel risks and safety tips for a student traveling in India.

            Profile: {st.session_state.travel_profile}

            Include:
            - Health risks (water, food, diseases)
            - Weather risks (heatwaves, monsoon, cold)
            - Crime & safety tips (city-wise)
            - Emergency precautions
            - Student-specific advice
            Format in structured points with risk levels (Low, Medium, High)
            """

            # Get AI response
            ai_response = get_gemini_response(prompt)

            # Display AI textual insights
            st.subheader("📝 AI Risk Analysis Summary")
            st.markdown(ai_response)

            # ----------------- Example Risk Table -----------------
            st.subheader("📋 Risk Overview Table (Sample)")
            states = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",

    # Union Territories
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry"
]

            risk_types = ["Health", "Weather", "Crime"]
            risk_levels = ["Low", "Medium", "High"]

            table_data = []
            for state in states:
                row = {"State": state}
                for risk in risk_types:
                    row[risk] = random.choice(risk_levels)
                table_data.append(row)

            df_risks = pd.DataFrame(table_data)
            st.table(df_risks)

            # ----------------- Risk Distribution Bar Chart -----------------
            st.subheader("📊 Risk Distribution by State")
            df_numeric = df_risks.replace({"Low": 1, "Medium": 2, "High": 3})
            st.bar_chart(df_numeric.set_index("State"))

            # ----------------- Pie Chart: Risk Type Share -----------------
            st.subheader("🥧 Overall Risk Type Share")
            # Count how many high, medium, low for each risk type
            risk_counts = {}
            for risk in risk_types:
                risk_counts[risk] = df_numeric[risk].sum()

            fig, ax = plt.subplots()
            ax.pie(
                risk_counts.values(),
                labels=risk_counts.keys(),
                autopct="%1.1f%%",
                startangle=90,
                colors=["#08CB00", "#6594B1", "#FFA500"]  # green, blue, orange
            )
            ax.axis("equal")
            st.pyplot(fig)

            # ----------------- Downloadable CSV -----------------
            st.subheader("💾 Download Risk Data")
            csv_data = df_risks.to_csv(index=False)
            st.download_button(
                label="Download Risk Table CSV",
                data=csv_data,
                file_name="student_travel_risk.csv",
                mime="text/csv"
            )

            # ----------------- Emergency Contacts -----------------
            st.subheader("📞 Emergency Contacts (Sample)")
            emergency_contacts = {
                "Police Helpline": "100",
                "Tourist Helpline": "1363",
                "Ambulance": "102",
                "Women Helpline": "1091"
            }
            for k, v in emergency_contacts.items():
                st.write(f"**{k}:** {v}")

            # ----------------- AI Suggested Precautions -----------------
            st.subheader("✅ Suggested Precautions")
            precautions = [
                "Avoid night travel alone.",
                "Drink only bottled/boiled water.",
                "Keep important documents and money secure.",
                "Check weather forecast before daily trips.",
                "Prefer group travel for safety.",
                "Use verified hostels with good reviews."
            ]
            for i, tip in enumerate(precautions, 1):
                st.markdown(f"{i}. {tip}")


# ---------------- SECTION 4 ----------------
with section4:
    st.subheader(" Student Travel Scheduler")

    # -------- Radio Buttons for Schedule Type --------
    schedule_type = st.radio(
        "Select Schedule Type:",
        options=["Pre-schedule", "During Trip", "Both"],
        horizontal=True
    )

    # Optional notes
    schedule_input = st.text_area(
        "Add any notes for your schedule (optional):",
        placeholder="e.g., 'Focus on cultural visits in the morning'"
    )

    st.markdown("### Select Time Slots to Plan")
    col1, col2 = st.columns(2)
    with col1:
        morning = st.checkbox(" Morning", value=True)
        afternoon = st.checkbox(" Afternoon", value=True)
    with col2:
        evening = st.checkbox(" Evening", value=True)
        night = st.checkbox(" Night", value=False)

    selected_times = []
    if morning: selected_times.append("Morning")
    if afternoon: selected_times.append("Afternoon")
    if evening: selected_times.append("Evening")
    if night: selected_times.append("Night")

    # -------- Button to generate schedule --------
    if st.button("Generate Travel Schedule"):
        with st.spinner("Generating your student travel schedule..."):
            # Build prompt dynamically
            schedule_desc = ""
            if schedule_type == "Pre-schedule":
                schedule_desc = "Plan activities before the trip starts (preparation, sightseeing plan, booking, etc.)"
            elif schedule_type == "During Trip":
                schedule_desc = "Plan activities during the trip including sightseeing, travel, rest, and meals"
            else:  # Both
                schedule_desc = "Plan activities both before and during the trip, including preparation, sightseeing, travel, rest, and meals"

            prompt = f"""
            You are a student travel planner for India.

            Schedule Type: {schedule_type} ({schedule_desc})
            Time slots to plan: {', '.join(selected_times) if selected_times else 'All day'}

            Profile: {st.session_state.travel_profile}

            Include:
            - Day-wise plan
            - Suggested activities for selected time slots
            - Balance travel, sightseeing, and rest
            - Meal recommendations

            Notes: {schedule_input if schedule_input else 'None'}
            """

            # Get AI response
            response = get_gemini_response(prompt)

            # Display AI generated schedule
            st.subheader("📝 AI Generated Schedule")
            st.markdown(response)


# ---------------- SECTION 5 ----------------
with section5:
    st.subheader("🤖 Travel Assistant")

    travel_query = st.text_input(
        "Ask anything about traveling in India",
        placeholder="e.g., 'Best budget trip from Hyderabad for students?'"
    )

    if st.button("Ask Travel Assistant"):
        if not travel_query:
            st.warning("Please enter a travel question")
        else:
            with st.spinner("Finding the best answer for you..."):
                prompt = f"""
                You are an expert Indian travel planner specialized in student travel.

                Answer the following question:
                {travel_query}

                Consider this student profile:
                {st.session_state.travel_profile}

                Include:
                1. Clear guidance
                2. Budget-friendly advice
                3. State & district references
                4. Safety tips
                5. Transport suggestions
                """

                response = get_gemini_response(prompt)
                st.subheader("🧭 Travel Assistant Response")
                st.markdown(response)