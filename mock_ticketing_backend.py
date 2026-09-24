"""Mock Ticketing Backend and Database Services.

Simulates production ticketing services for:
1. Customer Account & Booking Management (Customer Experience)
2. Voice Identity Verification (Security & Fraud Prevention)
3. Finance & Ops Refund Ledger & Payment Gateway Processing
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


@dataclass
class BookingRecord:
    """Movie ticket booking details."""
    booking_id: str
    customer_name: str
    phone_number: str
    movie_title: str
    format: str  # e.g., IMAX 2D, 4DX, 2D
    language: str
    cinema_name: str
    screen_audi: str
    showtime: datetime
    seat_numbers: List[str]
    seat_category: str  # Platinum, Gold, Recliner
    ticket_amount: float
    convenience_fee: float
    total_paid: float
    payment_method: str  # UPI, CREDIT_CARD, DIGITAL_WALLET
    status: str = "CONFIRMED"  # CONFIRMED, CANCELLED, COMPLETED
    cancellation_eligible: bool = True
    cancellation_fee: float = 100.0  # Standard cancellation policy deduction
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RefundRecord:
    """Finance & Ops Refund Transaction details."""
    refund_id: str
    booking_id: str
    customer_phone: str
    original_amount: float
    cancellation_fee: float
    net_refund_amount: float
    refund_destination: str  # ORIGINAL_PAYMENT_METHOD, INSTANT_WALLET
    status: str  # PROCESSED, PENDING, FAILED
    processed_at: datetime
    finance_reference: str
    notes: str


class TicketingBackendService:
    """In-memory backend simulating ticketing microservices."""

    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        # Sample upcoming bookings
        self.bookings: Dict[str, BookingRecord] = {
            "TKT-882190": BookingRecord(
                booking_id="TKT-882190",
                customer_name="Rahul Sharma",
                phone_number="+919876543210",
                movie_title="Dune: Part Two",
                format="IMAX 2D",
                language="English",
                cinema_name="PVR Director's Cut, Ambience Mall, Gurugram",
                screen_audi="Audi 2 (IMAX)",
                showtime=now + timedelta(hours=3, minutes=30),
                seat_numbers=["D12", "D13"],
                seat_category="Platinum Recliner",
                ticket_amount=1200.0,
                convenience_fee=150.0,
                total_paid=1350.0,
                payment_method="HDFC Credit Card ending in 4092",
                status="CONFIRMED",
                cancellation_eligible=True,
                cancellation_fee=150.0,
            ),
            "TKT-774412": BookingRecord(
                booking_id="TKT-774412",
                customer_name="Priya Patel",
                phone_number="+919123456789",
                movie_title="Deadpool & Wolverine",
                format="3D",
                language="Hindi",
                cinema_name="INOX Megaplex, Inorbit Mall, Malad, Mumbai",
                screen_audi="Audi 4",
                showtime=now + timedelta(days=1, hours=4),
                seat_numbers=["H8", "H9", "H10"],
                seat_category="Gold Executive",
                ticket_amount=1800.0,
                convenience_fee=220.0,
                total_paid=2020.0,
                payment_method="Google Pay UPI (priya@oksbi)",
                status="CONFIRMED",
                cancellation_eligible=True,
                cancellation_fee=180.0,
            ),
            "TKT-339901": BookingRecord(
                booking_id="TKT-339901",
                customer_name="Rahul Sharma",
                phone_number="+919876543210",
                movie_title="Stree 2",
                format="2D",
                language="Hindi",
                cinema_name="Cinepolis, DLF Avenue, Saket, New Delhi",
                screen_audi="Audi 1",
                showtime=now - timedelta(days=2),
                seat_numbers=["B4", "B5"],
                seat_category="Silver",
                ticket_amount=700.0,
                convenience_fee=80.0,
                total_paid=780.0,
                payment_method="Paytm UPI",
                status="COMPLETED",
                cancellation_eligible=False,
                cancellation_fee=0.0,
            ),
        }

        # Active voice verification challenges: booking_id -> {otp, phone, expires_at, verified, token}
        self.active_otps: Dict[str, dict] = {
            "TKT-882190": {
                "otp": "4829",
                "phone_number": "+919876543210",
                "expires_at": time.time() + 3600,
                "verified": False,
                "token": None,
            },
            "TKT-774412": {
                "otp": "6150",
                "phone_number": "+919123456789",
                "expires_at": time.time() + 3600,
                "verified": False,
                "token": None,
            },
        }

        # Finance & Ops Refund Ledger
        self.refund_ledger: Dict[str, RefundRecord] = {}

    def get_booking(self, booking_id: str) -> Optional[BookingRecord]:
        """Fetch booking by ID (case-insensitive)."""
        normalized_id = booking_id.strip().upper().replace("BMS-", "TKT-")
        return self.bookings.get(normalized_id)

    def find_bookings_by_phone(self, phone: str) -> List[BookingRecord]:
        """Find all bookings registered to a phone number."""
        clean_phone = phone.replace(" ", "").replace("-", "")
        return [
            b for b in self.bookings.values()
            if clean_phone in b.phone_number.replace(" ", "").replace("-", "")
        ]

    def generate_voice_otp(self, booking_id: str, phone_number: str) -> dict:
        """Generate a 4-digit voice verification OTP for identity confirmation."""
        booking = self.get_booking(booking_id)
        if not booking:
            return {"success": False, "error": f"Booking ID '{booking_id}' not found."}

        otp = "4829" if booking.booking_id == "TKT-882190" else "6150"
        self.active_otps[booking.booking_id] = {
            "otp": otp,
            "phone_number": phone_number or booking.phone_number,
            "expires_at": time.time() + 600,
            "verified": False,
            "token": None,
        }
        return {
            "success": True,
            "booking_id": booking.booking_id,
            "masked_phone": booking.phone_number[:6] + "XXXX" + booking.phone_number[-2:],
            "voice_otp": otp,
            "instructions": (
                f"A 4-digit verification code has been sent to {booking.phone_number[-4:]}. "
                f"For this IVR session, the caller can read out code: '{otp}'."
            ),
        }

    def verify_voice_identity(self, booking_id: str, spoken_otp: str) -> dict:
        """Verify the caller's spoken OTP to authorize financial actions."""
        booking = self.get_booking(booking_id)
        if not booking:
            return {"verified": False, "error": f"Booking ID '{booking_id}' not found."}

        challenge = self.active_otps.get(booking.booking_id)
        if not challenge:
            return {
                "verified": False,
                "error": "No active verification challenge found. Please request a verification OTP first.",
            }

        if time.time() > challenge["expires_at"]:
            return {"verified": False, "error": "Verification code has expired. Please request a new code."}

        clean_spoken = "".join(filter(str.isdigit, spoken_otp))
        expected = challenge["otp"]

        if clean_spoken == expected or spoken_otp.strip() == expected:
            token = f"VTOK-{uuid.uuid4().hex[:12].upper()}"
            challenge["verified"] = True
            challenge["token"] = token
            return {
                "verified": True,
                "verification_token": token,
                "customer_name": booking.customer_name,
                "message": "Voice identity verification successful. You are authorized to proceed with ticket cancellation.",
            }
        else:
            return {
                "verified": False,
                "error": f"Invalid verification code. Caller spoke '{spoken_otp}', but it does not match registered OTP.",
            }

    def process_cancellation_and_refund(
        self,
        booking_id: str,
        verification_token: str,
        refund_destination: str = "ORIGINAL_PAYMENT_METHOD",
        cancellation_reason: str = "Customer requested via IVR",
    ) -> dict:
        """Process cancellation and trigger automated refund with Finance & Ops ledger."""
        booking = self.get_booking(booking_id)
        if not booking:
            return {"success": False, "error": f"Booking '{booking_id}' not found."}

        if booking.status == "CANCELLED":
            return {
                "success": False,
                "error": f"Booking '{booking_id}' has already been cancelled previously.",
            }

        if not booking.cancellation_eligible:
            return {
                "success": False,
                "error": "Booking is not eligible for cancellation. Show cutoff time has passed.",
            }

        challenge = self.active_otps.get(booking.booking_id)
        if not challenge or not challenge.get("verified") or challenge.get("token") != verification_token:
            return {
                "success": False,
                "error": "Unauthorized: Voice identity verification token is missing or invalid. Identity must be verified before refund.",
            }

        cancellation_fee = booking.cancellation_fee
        net_refund = max(0.0, booking.ticket_amount - cancellation_fee)

        refund_id = f"RFND-TKT-{uuid.uuid4().hex[:8].upper()}"
        finance_ref = f"FIN-TXN-{uuid.uuid4().hex[:10].upper()}"

        refund_record = RefundRecord(
            refund_id=refund_id,
            booking_id=booking.booking_id,
            customer_phone=booking.phone_number,
            original_amount=booking.total_paid,
            cancellation_fee=cancellation_fee,
            net_refund_amount=net_refund,
            refund_destination=refund_destination,
            status="PROCESSED",
            processed_at=datetime.now(timezone.utc),
            finance_reference=finance_ref,
            notes=f"Reason: {cancellation_reason}. Method: {booking.payment_method}",
        )

        booking.status = "CANCELLED"
        booking.cancellation_eligible = False
        self.refund_ledger[refund_id] = refund_record

        del self.active_otps[booking.booking_id]

        eta_timeline = (
            "Instant credit to Digital Wallet"
            if "WALLET" in refund_destination.upper()
            else "3 to 5 business days back to your original payment method (" + booking.payment_method + ")"
        )

        return {
            "success": True,
            "refund_id": refund_id,
            "booking_id": booking.booking_id,
            "movie_title": booking.movie_title,
            "original_amount_paid": booking.total_paid,
            "cancellation_fee_deducted": cancellation_fee,
            "net_refund_amount": net_refund,
            "refund_destination": refund_destination,
            "finance_reference": finance_ref,
            "timeline": eta_timeline,
            "confirmation_sms": f"Sent to {booking.phone_number}",
            "message": (
                f"Ticket for '{booking.movie_title}' has been successfully cancelled. "
                f"A net refund of ₹{net_refund:.2f} has been initiated (Refund Reference: {refund_id}). "
                f"The amount will reflect via {eta_timeline}."
            ),
        }


ticketing_backend = TicketingBackendService()
