"use client";
import React, { useEffect, useRef, useState } from "react";
import Head from "next/head";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Breadcrumb from "@/components/ui/Breadcrumb";
import {
  TrashIcon,
  PlusIcon,
  UploadIcon,
  FileIcon,
  LinkIcon,
  SearchIcon,
  DownloadIcon,
  PencilIcon,
} from "lucide-react";
import TabList from "@/components/ui/TabList";
import ProcessesList from "@/components/ProcessesList";
import Title from "@/components/ui/Title";
import Drawer from "@/components/ui/Drawer";
import {
  AddProjectAsset,
  GetProject,
  GetProjectAssets,
  AddProjectURLAsset,
} from "@/services/projects";
import { ProjectData } from "@/interfaces/projects";
import {
  useQuery,
  useQueryClient,
  useInfiniteQuery,
} from "@tanstack/react-query";
import DragAndDrop from "@/components/DragAndDrop";
import DragOverlay from "@/components/DragOverlay";
import { Table, Column } from "@/components/ui/Table";
import ConfirmationDialog from "@/components/ConfirmationDialog";
import { useDeleteAssets } from "@/hooks/useProjects";
import DateLabel from "@/components/ui/Date";
import { Button } from "@/components/ui/Button";
import AssetUploadModal from "@/components/AssetUploadModal";
import { AssetData } from "@/interfaces/assets";
import AssetViewer from "@/components/AssetViewer";
import Tooltip from "@/components/ui/Tooltip";
import { BASE_STORAGE_URL } from "@/constants";
import PageLoader from "@/components/ui/PageLoader";
import toast from "react-hot-toast";
import { formatFileSize } from "@/lib/utils";
import RecentTransformations from "@/components/RecentTransformations";
import Link from "next/link";
import { useInView } from "react-intersection-observer";
import { Loader2 } from "lucide-react";

export default function Project() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = searchParams?.get("tab") ?? "assets";
  const isProcesses = searchParams?.get("processes") ?? null;
  const id = params?.projectId as string;
  const [activeTab, setActiveTab] = useState<string>(tab);
  const [uploadingFile, setUploadingFile] = useState<boolean>(false);
  const [currentAsset, setCurrentAsset] = useState<AssetData | null>(null);
  const [currentAssetPreview, setCurrentAssetPreview] = useState<
    AssetData | Blob | null
  >(null);
  const [pageSize] = useState(20);
  const [deletedId, setDeletedId] = useState("");
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<[string, Date][]>([]);
  const [openUploadModal, setOpenUploadModal] = useState<boolean>(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [processType, setProcessType] = useState<string | null>(null);
  const { ref, inView } = useInView();

  const queryClient = useQueryClient();

  const {
    data: project,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["project", id],
    queryFn: async () => {
      const response = await GetProject(id);
      const { data: project } = response.data;
      setProcessType(project.process_type);
      return project as ProjectData;
    },
    refetchInterval: 15000,
  });

  useEffect(() => {
    refetch();
  }, [id, refetch]);

  const {
    data: projectAssetsResponse,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading: isAssetsLoading,
    isFetching: isAssetsFetching,
    refetch: refetchAssets,
  } = useInfiniteQuery({
    queryKey: ["projectAssets", id],
    queryFn: ({ pageParam = 1 }) => GetProjectAssets(id, pageParam, pageSize),
    getNextPageParam: (lastPage, allPages) => {
      const nextPage = allPages.length + 1;
      return lastPage.data.total_count > allPages.length * pageSize
        ? nextPage
        : undefined;
    },
    initialPageParam: 1,
  });

  const { mutateAsync: deleteAsset, isPending: isDeleteAssetPending } =
    useDeleteAssets();

  const assets = projectAssetsResponse?.pages.flatMap((page) => page.data.data)
    ? projectAssetsResponse?.pages
        .flatMap((page) => page.data.data)
        .map((asset: AssetData) => {
          return {
            ...asset,
            size: asset.size ? formatFileSize(asset.size) : "-",
          };
        })
    : [];

  const projectTabs = [
    { id: "assets", label: "Docs" },
    { id: "processes", label: "Processes" },
  ];

  const breadcrumbItems = [
    { label: "Projects", href: "/" },
    { label: project?.name || "", href: `/projects/${project?.id}` },
  ];

  const openPreview = async (asset: AssetData) => {
    if (project) {
      setCurrentAsset(asset);
      if (typeof asset.id == "string") {
        const file_obj = uploadingFiles.find(
          (value) => value.name === asset.id
        );
        if (file_obj) {
          const file_blob = new Blob([file_obj], { type: file_obj.type });
          setCurrentAssetPreview(file_blob);
        } else {
          console.error("File not found in uploadingFiles.");
        }
      } else {
        const assetExtracted = assets.find((value) => value.id === asset.id);
        if (assetExtracted) {
          setCurrentAssetPreview({
            id: assetExtracted.id,
            filename: assetExtracted.filename,
            path: assetExtracted.path,
            type: assetExtracted.type,
            size: Number(assetExtracted.size),
            details: assetExtracted.details,
            updated_at: assetExtracted.updated_at,
            created_at: assetExtracted.created_at,
          });
        } else {
          console.error("Asset not found in assets array.");
        }
      }
    }
  };

  const startDownload = async (row: AssetData) => {
    try {
      const response = await fetch(
        `${BASE_STORAGE_URL}/${project?.id}/${row.filename}`
      );
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = row.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading file:", error);
    }
  };

  const newProcess = () => {
    router.push(`/projects/${id}/processes/new`);
  };

  const handleFileUpload = async (fileList: FileList | null) => {
    if (fileList) {
      setUploadingFile(true);
      const files = Array.from(fileList);
      setUploadingFiles((prev) => [...prev, ...files]);

      try {
        for (const file of files) {
          const response = await AddProjectAsset(id, file);

          if (!response.data) {
            throw new Error("Failed to upload file");
          }
          setUploadedFiles((prev) => [...prev, [file.name, new Date()]]);
        }
        setUploadingFile(false);
        setUploadingFiles([]);
        setUploadedFiles([]);
        refetchAssets();
      } catch (error) {
        console.error("Error uploading files:", error);
        setUploadingFiles([]);
        setUploadedFiles([]);
        setUploadingFile(false);
      }
    }
  };

  const columns: Column<(typeof assets)[0]>[] = [
    {
      header: "File name",
      accessor: "filename",
      label: (data: { type?: string; filename: string }) => (
        <div className="flex items-center">
          {data.type?.includes("pdf") ? (
            <Tooltip content="PDF" delay={1000}>
              <FileIcon className="mr-2 h-4 w-4" />
            </Tooltip>
          ) : data.type?.includes("url") ? (
            <Tooltip content="Website">
              <LinkIcon className="mr-2 h-4 w-4" />
            </Tooltip>
          ) : null}
          {data.filename}
        </div>
      ),
    },
    { header: "Size", accessor: "size" },
    {
      header: "Last modified",
      accessor: "updated_at",
      label: (data: { updated_at: string }) => (
        <DateLabel dateString={data.updated_at} />
      ),
    },
  ];

  useEffect(() => {
    if (isProcesses) {
      setActiveTab("processes");
    }
  }, [isProcesses]);

  const handleDelete = () => {
    deleteAsset(
      { projectId: project?.id!, assetId: deletedId! },
      {
        onSuccess() {
          setIsDeleteModalOpen(false);
          toast.success("Asset successfully deleted.");
          queryClient.invalidateQueries({ queryKey: ["projectAssets"] });
        },
        onError(error) {
          console.log(error);
        },
      }
    );
  };

  const onUploadSubmit = async (
    type: string,
    data: string[] | FileList | null
  ) => {
    if (type == "file") {
      handleFileUpload(data as FileList);
    } else if (type == "url") {
      const response = await AddProjectURLAsset(id, data as string[]);
      if (!response.data) {
        return false;
      }
      queryClient.invalidateQueries({ queryKey: ["projectAssets"] });
    }

    setOpenUploadModal(false);
    return true;
  };

  useEffect(() => {
    if (inView && hasNextPage) {
      fetchNextPage();
    }
  }, [inView, fetchNextPage, hasNextPage]);

  const shouldShowDragAndDrop =
    !uploadingFile &&
    !isAssetsLoading &&
    !isAssetsFetching &&
    (!assets || assets.length === 0);

  return (
    <>
      <Head>
        <title>{`PandaETL - ${project?.name}`}</title>
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <Breadcrumb items={breadcrumbItems} classNames="mb-8" />

      <div className="mb-8">
        <div className="flex items-center group">
          <Title margin={false}>{project?.name}</Title>
          <Link
            href={`/projects/${id}/edit`}
            className="ml-2 mt-1 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <PencilIcon className="h-4 w-4" />
            <span className="sr-only">Edit project</span>
          </Link>
        </div>
        {project?.description && (
          <p className="text-gray-600 mt-2 text-sm leading-relaxed max-w-2xl">
            {project?.description}
          </p>
        )}
      </div>

      {isLoading || isAssetsLoading ? (
        <PageLoader />
      ) : (
        <div ref={scrollRef}>
          {activeTab === "assets" && (
            <RecentTransformations projectId={project?.id} />
          )}
          <TabList
            tabs={projectTabs}
            onTabChange={(tabId) => setActiveTab(tabId)}
            defaultActiveTab={activeTab}
            actions={
              <div className="flex gap-2">
                {activeTab === "assets" && (
                  <Button
                    onClick={() => setOpenUploadModal(true)}
                    icon={UploadIcon}
                    variant="light"
                  >
                    Add docs
                  </Button>
                )}
                {(assets && assets.length == 0) || assets == undefined ? (
                  <Tooltip content="Add docs to the project before running a process">
                    <Button
                      onClick={newProcess}
                      icon={PlusIcon}
                      disabled={true}
                    >
                      New process
                    </Button>
                  </Tooltip>
                ) : (
                  <Button onClick={newProcess} icon={PlusIcon}>
                    New process
                  </Button>
                )}
              </div>
            }
          />

          {activeTab === "assets" && (
            <>
              {shouldShowDragAndDrop ? (
                <DragAndDrop
                  onFileSelect={handleFileUpload}
                  accept={[".pdf", "application/pdf"]}
                />
              ) : (
                <>
                  <Table
                    data={assets || []}
                    columns={columns}
                    onRowClick={(row) => openPreview(row)}
                    actions={[
                      {
                        label: "Preview",
                        icon: <SearchIcon className="mx-1 h-4 w-4" />,
                        onClick: (row) => openPreview(row),
                      },
                      {
                        label: "Download",
                        icon: <DownloadIcon className="mx-1 h-4 w-4" />,
                        onClick: (row) => {
                          startDownload(row);
                        },
                      },
                      {
                        label: "Delete",
                        icon: <TrashIcon className="mx-1 h-4 w-4" />,
                        onClick: (row) => {
                          setDeletedId(row.id);
                          setIsDeleteModalOpen(true);
                        },
                      },
                    ]}
                    uploadingFiles={uploadingFiles}
                    uploadedFiles={uploadedFiles}
                    isAssetsLoading={isAssetsLoading}
                  />
                  {hasNextPage && (
                    <div ref={ref} className="flex justify-center py-4">
                      {isFetchingNextPage ? (
                        <Loader2 className="h-6 w-6 animate-spin" />
                      ) : (
                        <Button onClick={() => fetchNextPage()} variant="light">
                          Load More
                        </Button>
                      )}
                    </div>
                  )}
                </>
              )}

              {activeTab === "assets" && assets && assets.length > 0 && (
                <DragOverlay
                  onFileDrop={handleFileUpload}
                  accept={[".pdf", "application/pdf"]}
                />
              )}
            </>
          )}
          {activeTab === "processes" && (
            <ProcessesList projectId={project?.id} />
          )}

          <Drawer
            isOpen={currentAssetPreview !== null}
            onClose={() => setCurrentAssetPreview(null)}
            title={currentAsset?.filename}
          >
            {currentAssetPreview && project && (
              <AssetViewer
                project_id={project.id}
                asset={currentAssetPreview}
              />
            )}
          </Drawer>
        </div>
      )}

      {isDeleteModalOpen && (
        <ConfirmationDialog
          text="Are you sure you want to delete this asset?"
          onCancel={() => {
            setIsDeleteModalOpen(false);
          }}
          isLoading={deleteLoading}
          onSubmit={handleDelete}
        />
      )}

      {openUploadModal && (
        <AssetUploadModal
          isOpen={openUploadModal}
          project_id={project?.id}
          onSubmit={onUploadSubmit}
          onCancel={() => setOpenUploadModal(false)}
        />
      )}
    </>
  );
}
