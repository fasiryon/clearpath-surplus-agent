import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({
    hasSupabaseUrl: Boolean(process.env.SUPABASE_URL),
    hasServiceKey: Boolean(process.env.SUPABASE_SERVICE_KEY),
    supabaseUrlLength: process.env.SUPABASE_URL?.length ?? 0,
    serviceKeyLength: process.env.SUPABASE_SERVICE_KEY?.length ?? 0,
    nodeEnv: process.env.NODE_ENV,
  });
}
