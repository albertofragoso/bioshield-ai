import { NextRequest, NextResponse } from "next/server";

const AUTH_ROUTES = ["/login", "/register"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasToken = request.cookies.has("access_token");
  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));

  // Autenticado intentando acceder a login/register → dashboard
  if (isAuthRoute && hasToken) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // No autenticado intentando acceder a ruta protegida → login
  if (!isAuthRoute && !hasToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const proxyConfig = {
  // Excluir archivos estáticos, imágenes de Next.js y assets de /public
  matcher: ["/((?!_next/static|_next/image|favicon.ico|avatars/).*)"],
};
