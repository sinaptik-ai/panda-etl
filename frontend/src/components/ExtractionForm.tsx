"use client";
import { useState, FormEvent, useRef } from "react";
import {
  ChevronDown,
  Loader2,
  Play,
  Plus,
  ScanEye,
  LayoutTemplate,
  Sparkles,
  Trash2,
  Save,
} from "lucide-react";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { ProcessData, ProcessSuggestionRequest } from "@/interfaces/processes";
import { ProcessSelectionDrawer } from "./ProcessSelectionDrawer";
import { ExtractionField } from "@/interfaces/extract";
import AddFieldsAIDrawer from "./AddFieldsAIDrawer";
import { Card } from "@/components/ui/Card";
import Switch from "./ui/Switch";
import toast from "react-hot-toast";

const FIELD_TYPES = ["text", "number", "date", "list"] as const;

type FieldType = (typeof FIELD_TYPES)[number];

interface Field {
  key: string;
  description: string;
  type: FieldType;
}

interface ExtractionFormProps {
  onSubmit: (fields: Field[]) => Promise<void>;
  onStartProcess: (fields: Field[], multiFields: boolean) => Promise<void>;
  fields: Field[];
  setFields: React.Dispatch<React.SetStateAction<Field[]>>;
  processData: ProcessSuggestionRequest;
  multiField: boolean;
}

export default function ExtractionForm({
  onSubmit,
  onStartProcess,
  fields,
  setFields,
  processData,
  multiField,
}: ExtractionFormProps) {
  const [expandedFields, setExpandedFields] = useState<Record<number, boolean>>(
    { 0: true }
  );
  const [isLoading, setIsLoading] = useState(false);
  const [displayPsModel, setDisplayPsModel] = useState<boolean>(false);
  const [displayAIFieldsModel, setDisplayAIFieldsModel] =
    useState<boolean>(false);
  const [startingProcess, setStartingProcess] = useState<boolean>(false);
  const fieldRefs = useRef<(HTMLInputElement | null)[]>([]);
  const [multiFields, setMultiFields] = useState<boolean>(multiField);

  const addField = () => {
    const newField: Field = { key: "", description: "", type: "text" };
    const newIndex = fields.length;

    setFields((prevFields) => [...prevFields, newField]);

    setExpandedFields((prev) => {
      const newState = { ...prev };
      Object.keys(newState).forEach((key) => {
        newState[Number(key)] = false;
      });
      newState[newIndex] = true;
      return newState;
    });

    setTimeout(() => {
      fieldRefs.current[newIndex]?.focus();
    }, 300);
  };

  const removeField = (index: number) => {
    const newFields = [...fields];
    newFields.splice(index, 1);
    setFields(newFields);

    const newExpandedFields = { ...expandedFields };
    delete newExpandedFields[index];
    setExpandedFields(newExpandedFields);
  };

  const updateField = (
    index: number,
    key: keyof Field,
    value: FieldType | string
  ) => {
    const newFields = [...fields];
    if (key === "key") {
      value = value.replace(/\s+/g, "_").replace(/_+/g, "_").toLowerCase();
    }
    newFields[index][key] = value as any;
    setFields(newFields);
  };

  const is_fields_empty = () => {
    return (
      (fields.length == 1 &&
        fields[0].key == "" &&
        fields[0].description == "") ||
      fields.length == 0
    );
  };

  const onStartBtnClick = async () => {
    try {
      setStartingProcess(true);
      await onStartProcess(fields, multiFields);
      setStartingProcess(false);
    } catch (error) {
      console.error("Error start process:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await onSubmit(fields);
    } catch (error) {
      toast.error(
        "The file isn't ready for preview yet, preprocessing is in progress."
      );
      console.error("Error submitting form:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAIFieldsBtn = () => {
    setDisplayAIFieldsModel(true);
  };

  const onAIFieldBtnClose = () => {
    setDisplayAIFieldsModel(false);
  };

  const onCancel = async () => {
    setDisplayPsModel(false);
  };

  const handleAIFieldsSubmit = (data: ExtractionField[]) => {
    if (data.length > 0) {
      if (fields.length == 1) {
        setFields(data);
      } else {
        setFields((prevFields) => [...prevFields, ...data]);
      }
    }
    onAIFieldBtnClose();
  };

  const handleProcessSuggestion = async () => {
    setDisplayPsModel(true);
  };

  const handleProcessTemplate = async (template: ProcessData | null) => {
    if (template) {
      setFields(template.details.fields);
      setDisplayPsModel(false);
    }
  };

  const toggleField = (index: number) => {
    setExpandedFields((prev) => {
      const newState = { ...prev, [index]: !prev[index] };
      if (newState[index]) {
        setTimeout(() => {
          fieldRefs.current[index]?.focus();
        }, 300);
      }
      return newState;
    });
  };

  const validateKey = (key: string) => {
    return /^[\p{L}\p{N}_ ]+$/u.test(key);
  };

  return (
    <>
      <style jsx>{`
        .collapsible-content {
          max-height: 0;
          overflow: hidden;
          transition:
            max-height 0.3s ease-out,
            opacity 0.3s ease-out;
          opacity: 0;
        }

        .collapsible-content.expanded {
          max-height: 1000px;
          opacity: 1;
          transition:
            max-height 0.5s ease-in,
            opacity 0.5s ease-in;
        }

        .chevron-icon {
          transition: transform 0.3s ease-in-out;
        }

        .chevron-icon.up {
          transform: rotate(180deg);
        }
      `}</style>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="mb-8">
          <div className="flex gap-4">
            <Button
              type="button"
              icon={Sparkles}
              onClick={handleAIFieldsBtn}
              variant="light"
              iconStyles="w-5 h-5 mr-2"
            >
              Generate Fields with AI
            </Button>

            <Button
              type="button"
              icon={LayoutTemplate}
              onClick={handleProcessSuggestion}
              variant="light"
              iconStyles="w-5 h-5 mr-2"
            >
              Use process as template
            </Button>
          </div>
        </div>
        <div className="flex justify-between items-center">
          <div>Enable multiple extractions for each file</div>
          <Switch onChange={setMultiFields} value={multiFields} />
        </div>
        <div className="space-y-6">
          {fields?.map((field, index) => (
            <Card
              key={index}
              size="nopadding"
              className="overflow-hidden border border-gray-200"
            >
              <div
                className="flex justify-between items-center px-6 py-4 cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors duration-200"
                onClick={() => toggleField(index)}
              >
                <span className="font-semibold text-lg">
                  {field.key || `Field ${index + 1}`}
                </span>
                <div
                  className={`chevron-icon ${
                    expandedFields[index] ? "up" : ""
                  }`}
                >
                  <ChevronDown size={24} className="text-gray-600" />
                </div>
              </div>
              <div
                className={`collapsible-content ${
                  expandedFields[index] ? "expanded" : ""
                }`}
              >
                <div className="p-6 space-y-4">
                  <Input
                    id={`field-key-${index}`}
                    ref={(el: HTMLInputElement | null) => {
                      fieldRefs.current[index] = el;
                    }}
                    label="Field key"
                    value={field.key}
                    onChange={(e) => updateField(index, "key", e.target.value)}
                    required
                    error={
                      field.key && !validateKey(field.key)
                        ? "Key can only contain letters, numbers, and underscores"
                        : ""
                    }
                  />
                  <Textarea
                    id={`field-description-${index}`}
                    label="Field description"
                    value={field.description}
                    onChange={(e) =>
                      updateField(index, "description", e.target.value)
                    }
                    rows={3}
                  />
                  <Select
                    id={`field-type-${index}`}
                    label="Field type"
                    value={field.type}
                    onChange={(e) =>
                      updateField(index, "type", e.target.value as FieldType)
                    }
                    options={FIELD_TYPES.map((type) => ({
                      value: type,
                      label: type.charAt(0).toUpperCase() + type.slice(1),
                    }))}
                  />
                  <div className="flex justify-end space-x-3 mt-4">
                    <Button
                      type="button"
                      onClick={() => removeField(index)}
                      variant="light"
                      className="text-sm"
                      icon={Trash2}
                    >
                      Remove
                    </Button>
                    <Button
                      type="button"
                      onClick={() => toggleField(index)}
                      variant="primary"
                      className="text-sm"
                      icon={Save}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
          <div
            className="bg-blue-50 rounded-lg shadow-md border-2 border-blue-200 hover:bg-blue-100 transition-colors duration-300 cursor-pointer"
            onClick={addField}
          >
            <div className="flex justify-between items-center px-6 py-4">
              <span className="text-lg font-semibold text-blue-600">
                Add new field
              </span>
              <Plus className="text-blue-600" size={24} />
            </div>
          </div>
        </div>
        <div className="flex justify-end space-x-4 mt-8">
          <Button
            type="submit"
            isLoading={isLoading}
            disabled={is_fields_empty()}
            icon={ScanEye}
            variant="secondary"
            className="px-6 py-2"
          >
            Preview
          </Button>
          <Button
            type="button"
            onClick={onStartBtnClick}
            icon={startingProcess ? Loader2 : Play}
            disabled={is_fields_empty()}
            variant="primary"
            className="px-6 py-2"
          >
            Start Process
          </Button>
        </div>
      </form>
      {displayPsModel && (
        <ProcessSelectionDrawer
          isOpen={displayPsModel}
          processData={processData}
          onCancel={onCancel}
          onSubmit={handleProcessTemplate}
        />
      )}
      {displayAIFieldsModel && (
        <AddFieldsAIDrawer
          isOpen={displayAIFieldsModel}
          project_id={processData.project_id}
          onSubmit={handleAIFieldsSubmit}
          onCancel={onAIFieldBtnClose}
        />
      )}
    </>
  );
}
