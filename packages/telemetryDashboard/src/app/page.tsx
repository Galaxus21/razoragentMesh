import { redirect } from "next/navigation";

const defaultRedirectRoute = "/overview";

export default function RootPage(): never {
  redirect(defaultRedirectRoute);
}
