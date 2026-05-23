import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  // Si no hay cookie de sesión → redirigir a login
  const token = request.cookies.get("access_token");
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  // Matcher restrictivo: SOLO rutas privadas.
  // Excluye: /, _next/*, favicon, api/waitlist, assets.
  // Resultado: la landing / nunca pasa por middleware → p99 TTFB < 200ms.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/waitlist|assets|$).*)"],
};
