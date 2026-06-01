import { NextRequest, NextResponse } from "next/server";

const AUTH_ROUTES = ["/login", "/register", "/privacy", "/terms"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasToken = request.cookies.has("access_token");
  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));

  if (isAuthRoute && hasToken) {
    return NextResponse.redirect(new URL("/home", request.url));
  }

  if (!isAuthRoute && !hasToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Excluye: / (landing pública), _next/*, favicon, api/waitlist, assets, avatars, demo (fixtures públicos).
  // La landing nunca pasa por proxy → TTFB óptimo.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/waitlist|assets|avatars|demo|$).*)"],
};
