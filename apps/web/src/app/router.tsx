import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppLayout } from "./shell/AppLayout";
import { HomePage } from "../features/home/HomePage";
import { IncidentDetailPage } from "../features/officer/IncidentDetailPage";
import { NeedWorkspacePage } from "../features/officer/NeedWorkspacePage";
import { OfficerBoardPage } from "../features/officer/OfficerBoardPage";
import { OfficerOverviewPage } from "../features/officer/OfficerOverviewPage";
import { ProblemDetailPage } from "../features/officer/ProblemDetailPage";
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
      { path: "officer", element: <OfficerBoardPage /> },
      { path: "officer/problems/:id", element: <ProblemDetailPage /> },

      // Superseded by the ward board and the problem detail page above, and kept
      // routed only so existing links resolve rather than hitting the error
      // boundary. They use the old "incident"/"need" vocabulary and come out with
      // the deletion pass in REBUILD_06 §2.
      { path: "officer/legacy", element: <OfficerOverviewPage /> },
      { path: "officer/incidents/:id", element: <IncidentDetailPage /> },
      { path: "officer/needs/:id", element: <NeedWorkspacePage /> },
    ],
  },
]);
