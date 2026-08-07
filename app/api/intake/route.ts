import { NextResponse } from "next/server";

export const runtime = "nodejs";

const allowedPreferences = new Set(["phone", "email"]);
const MAX_REQUEST_BYTES = 20_000;

function text(value: unknown, maxLength: number): string {
  return typeof value === "string" ? value.trim().slice(0, maxLength) : "";
}

function validEmail(value: string): boolean {
  return !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function validPhone(value: string): boolean {
  return !value || value.replace(/\D/g, "").length >= 10;
}

export async function POST(request: Request) {
  let body: Record<string, unknown>;

  const contentLength = Number(request.headers.get("content-length") || "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_REQUEST_BYTES) {
    return NextResponse.json({ message: "This request is too large." }, { status: 413 });
  }

  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ message: "Please check the form and try again." }, { status: 400 });
  }

  if (text(body.website, 200)) {
    return NextResponse.json({ message: "Your request was received." });
  }

  const fullName = text(body.fullName, 120);
  const phone = text(body.phone, 30);
  const email = text(body.email, 254).toLowerCase();
  const propertyAddress = text(body.propertyAddress, 300);
  const county = text(body.county, 100);
  const caseNumber = text(body.caseNumber, 80);
  const notes = text(body.notes, 1200);
  const preference = text(body.contactPreference, 20);
  const consent = body.consent === "yes";

  if (!fullName || !propertyAddress || !consent || (!phone && !email)) {
    return NextResponse.json(
      { message: "Please provide your name, property address, consent, and either a phone number or email." },
      { status: 400 },
    );
  }

  if (!validEmail(email) || !validPhone(phone) || !allowedPreferences.has(preference)) {
    return NextResponse.json({ message: "Please check your contact information and try again." }, { status: 400 });
  }

  if ((preference === "phone" && !phone) || (preference === "email" && !email)) {
    return NextResponse.json(
      { message: "Please provide the contact method you selected." },
      { status: 400 },
    );
  }

  const supabaseUrl = process.env.SUPABASE_URL?.replace(/\/$/, "");
  const serviceKey = process.env.SUPABASE_SERVICE_KEY;

  if (!supabaseUrl || !serviceKey) {
    console.error("Intake unavailable: SUPABASE_URL or SUPABASE_SERVICE_KEY is missing");
    return NextResponse.json(
      { message: "The request form is temporarily unavailable. Please try again shortly." },
      { status: 503 },
    );
  }

  const userAgent = text(request.headers.get("user-agent"), 500);
  const pageUrl = text(request.headers.get("referer"), 500);

  try {
    const response = await fetch(`${supabaseUrl}/rest/v1/claim_inquiries`, {
      method: "POST",
      headers: {
        apikey: serviceKey,
        Authorization: `Bearer ${serviceKey}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify({
        full_name: fullName,
        phone: phone || null,
        email: email || null,
        contact_preference: preference,
        property_address: propertyAddress,
        county: county || null,
        case_number: caseNumber || null,
        notes: notes || null,
        consent_to_contact: consent,
        source: "website",
        page_url: pageUrl || null,
        user_agent: userAgent || null,
      }),
      cache: "no-store",
    });

    if (!response.ok) {
      console.error(`Supabase intake insert failed with status ${response.status}`);
      return NextResponse.json(
        { message: "We could not save your request right now. Please try again shortly." },
        { status: 502 },
      );
    }
  } catch (error) {
    console.error("Supabase intake request failed", error instanceof Error ? error.message : "unknown error");
    return NextResponse.json(
      { message: "We could not save your request right now. Please try again shortly." },
      { status: 502 },
    );
  }

  return NextResponse.json({
    message: "A member of the ClearPath team will review the information and contact you using your preferred method.",
  });
}
