# Emreo - AI-Powered Emergency Response Optimizer for Ambulance Dispatch

## Overview

Emreo is a real-time emergency response optimization platform designed to improve ambulance dispatch efficiency during critical situations. The system intelligently assigns the most suitable ambulance based on incident severity, availability, and location.

The platform combines machine learning, real-time communication, and location-based tracking to simulate a modern emergency management system that can be extended for smart city and IoT-based healthcare infrastructure.

---

## Dashboard Preview

![Dashboard Preview](<img width="1542" height="947" alt="Screenshot 2026-04-23 000952" src="https://github.com/user-attachments/assets/f993425a-7907-4e39-8222-d7bef91b66c9" />)


---

## Key Features

### Intelligent Ambulance Dispatch
- Automatically identifies the nearest available ambulance
- Prioritizes incidents based on predicted severity
- Optimizes resource allocation during emergency situations

### Machine Learning-Based Severity Prediction
- XGBoost-based severity prediction
- SVM model integration
- Data-driven dispatch prioritization

### Real-Time Tracking
- Live ambulance location updates using WebSockets
- Dynamic status updates
- Continuous monitoring of active incidents

### Fleet Management
- Real-time ambulance availability tracking
- Operational status monitoring
- Resource allocation management

### Incident Management
- Report new emergencies
- Track incident lifecycle
- Historical incident records

---

## Screenshots

### Incident Reporting Panel

![Incident Severity and Current Status](<img width="351" height="809" alt="Screenshot 2026-04-23 001001 - Copy" src="https://github.com/user-attachments/assets/19a8d3da-ae99-48eb-9232-bef868a01959" />
)

---

### Available Fleet

![Available Fleet](<img width="336" height="826" alt="Screenshot 2026-04-23 001033" src="https://github.com/user-attachments/assets/b6f15443-7e6f-4df8-a3c9-b7cdf5eb631f" />
)

---

### Live Map Tracking

![Live Map Tracking](<img width="836" height="811" alt="Screenshot 2026-04-23 001012 - Copy" src="https://github.com/user-attachments/assets/a4c3a998-8475-441d-98a5-d1646a51a42d" />
)

---

### Log New Incident

![Log New Incident](<img width="619" height="566" alt="Screenshot 2026-04-23 001147" src="https://github.com/user-attachments/assets/66438454-dd14-4858-86fe-89b2a2d449db" />
)

---

## Tech Stack

### Frontend
- React.js
- JavaScript
- WebSocket Client

### Backend
- FastAPI
- Python

### Database
- SQLite
- SQLAlchemy

### Machine Learning
- XGBoost
- Scikit-learn
- Support Vector Machine (SVM)

### Real-Time Communication
- WebSockets

---

## System Architecture

### Frontend Layer
Interactive dashboard for monitoring incidents, ambulance locations, and dispatch operations.

### API Layer
FastAPI-based backend responsible for incident processing, ambulance allocation, and communication with the database.

### Machine Learning Layer
Predicts emergency severity and assists in dispatch prioritization.

### Real-Time Layer
WebSocket connections provide instant updates for fleet and incident tracking.

### Data Layer
SQLite database managed using SQLAlchemy.

---

## Core Functionalities

- Real-time ambulance dispatch
- Emergency severity prediction
- GPS simulation
- Fleet management
- Incident tracking
- WebSocket communication
- RESTful API services
- Route optimization logic

---

## Installation

### Clone Repository

```bash
git clone https://github.com/ayushsGaur/Emreo.git
cd Emreo
```

### Create and Activate Virtual Environment

```bash
python -m venv venv
```

Windows:

```bash
.\venv\Scripts\Activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment

```bash
$env:PYTHONPATH="."
```

---

## Running the Backend

```bash
python -m uvicorn backend.main:app --reload
```

Backend runs at:

```text
http://127.0.0.1:8000
```

---

## Seeding Sample Data

```bash
python scripts/seed.py
```

Reset and regenerate data:

```bash
python scripts/seed.py --wipe
```

---

## Running GPS Simulator

```bash
python scripts/gps_simulator.py
```

---

## Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Learning Outcomes

- Real-time application development using WebSockets
- FastAPI backend development
- Machine learning model integration
- Geolocation-based system design
- Event-driven architecture implementation
- Database management using SQLAlchemy
- Frontend and backend integration

---

## Future Enhancements

- Integration with real GPS devices
- Traffic-aware route optimization
- Hospital availability integration
- Mobile application support
- Cloud deployment
- Smart city infrastructure integration

---

## Author

**Ayush Anand**

---

## License

This project is intended for educational, research, and portfolio purposes.
