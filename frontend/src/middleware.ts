import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import localStorage from "@/lib/localStorage";
import { APIKeyData } from "./interfaces/user";
import axios from "axios";
import { GetAPIKey } from "./services/user";

export async function middleware(request: NextRequest) {
  let apiKey = null;
  try {
    const dockerBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

    if (dockerBackendUrl) {
      console.log(dockerBackendUrl);
      const response = await axios.get<{ data: APIKeyData }>(
        `${dockerBackendUrl}/v1/user/get-api-key`
      );
      apiKey = { data: { api_key: response.data.data.key } };
    } else {
      apiKey = await GetAPIKey();
    }
  } catch (error) {
    console.error("Error fetching API key:", error);
    return NextResponse.redirect(new URL("/api-key-setup", request.url));
  }

  if (!apiKey && !request.nextUrl.pathname.startsWith("/api-key-setup")) {
    console.log("No API key found. Redirecting to /api-key-setup");
    return NextResponse.redirect(new URL("/api-key-setup", request.url));
  }

  localStorage.setItem("api_key", apiKey.data.api_key);

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
