import { redirect } from "next/navigation";

/**
 * /settings — default route (server component).
 *
 * Settings routing lives at ``/settings/<tab>``. Plain ``/settings`` has
 * no dedicated landing page; redirect the caller to the General tab.
 *
 * Plan 07 Task 22.
 */
export default function SettingsPage(): never {
  redirect("/settings/general");
}
