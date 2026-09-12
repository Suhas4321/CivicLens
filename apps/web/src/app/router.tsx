import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppLayout } from "./shell/AppLayout";
import { HomePage } from "../features/home/HomePage";
import { IncidentDetailPage } from "../features/officer/IncidentDetailPage";
import { NeedWorkspacePage } from "../features/officer/NeedWorkspacePage";
import { OfficerOverviewPage } from "../features/officer/OfficerOverviewPage";
import { ReportPage } from "../features/report-intake/ReportPage";
import { ReceiptPage } from "../features/report-intake/ReceiptPage";
import { RouteErrorPage } from "./shell/RouteErrorPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "report", element: <ReportPage /> },
      { path: "receipt/:publicId", element: <ReceiptPage /> },
      { path: "demo", element: <Navigate replace to="/officer" /> },
      { path: "officer", element: <OfficerOverviewPage /> },
      { path: "officer/incidents/:id", element: <IncidentDetailPage /> },
      { path: "officer/needs/:id", element: <NeedWorkspacePage /> },
    ],
  },
]);
