"use client";
import React, { useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { GetProcess, processApiUrl } from "@/services/processes";
import { useQuery } from "@tanstack/react-query";
import LogoDark from "@/icons/LogoDark";
import { X, Download } from "lucide-react"; // Add Download icon
import DataTable from "@/components/DataTable";
import Papa from "papaparse";
import { BASE_API_URL } from "@/constants";
import { toast } from "react-hot-toast";
import { trackEvent } from "@/lib/mixpanelLib";

const ProcessPage = () => {
  const router = useRouter();
  const params = useParams<{
    projectId: string;
    processId: string;
  }>();
  const projectId = params?.projectId;
  const processId = params?.processId;
  const [csvData, setCsvData] = useState<Record<string, any>[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const { data: process } = useQuery({
    queryKey: ["process", processId],
    queryFn: () =>
      processId
        ? GetProcess(processId).then((response) => response.data.data)
        : Promise.reject("No processId"),
    enabled: !!processId,
  });

  const loadCsvData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `${BASE_API_URL}${processApiUrl}/${processId}/get-csv`
      );
      const {
        data: { csv },
      } = await response.json();

      Papa.parse(csv, {
        complete: (result: Papa.ParseResult<Record<string, any>>) => {
          if (
            !result.data ||
            !Array.isArray(result.data) ||
            result.data.length === 0
          ) {
            console.error("CSV data is empty or not in the expected format");
            return;
          }
          setCsvData(result.data);
          setIsLoading(false);
        },
        header: true,
      });

      trackEvent("Table opened", { url: `process_${processId}.csv` });
    } catch (error) {
      console.error("Error loading CSV data:", error);
      setIsLoading(false);
    }
  }, [processId]);

  const handleDownloadCsv = useCallback(async () => {
    try {
      const response = await fetch(
        `${BASE_API_URL}/${processApiUrl}/${processId}/download-csv`
      );
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `process_${processId}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      // Show success toast
      trackEvent("Download CSV", { url: `process_${processId}.csv` });
      toast.success("CSV downloaded successfully");
    } catch (error) {
      console.error("Error downloading CSV:", error);
      toast.error("Failed to download CSV");
    }
  }, [processId]);

  React.useEffect(() => {
    loadCsvData();
  }, [loadCsvData]);

  const handleClose = () => {
    router.push(`/projects/${projectId}`);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden">
      <header className="bg-gray-100 px-2 py-2 flex items-center justify-between shadow-sm border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <div className="mt-[2px]">
            <LogoDark width="48" height="48" />
          </div>
          <h1 className="text-lg font-semibold text-gray-800">
            {isLoading ? "Loading..." : `${process?.name}.csv` || "CSV Preview"}
          </h1>
        </div>
        <div className="space-x-2 flex items-center">
          <button
            onClick={handleDownloadCsv}
            className="text-gray-600 hover:text-gray-800 p-1 rounded-full hover:bg-gray-200"
            title="Download CSV"
          >
            <Download className="h-5 w-5" />
          </button>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-500 p-1 rounded-full hover:bg-gray-200"
            title="Close"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </header>
      <main className="flex-grow overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <p>Loading CSV data...</p>
          </div>
        ) : (
          <DataTable data={csvData} />
        )}
      </main>
    </div>
  );
};

export default ProcessPage;
