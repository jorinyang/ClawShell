"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Clock, CheckCircle, AlertTriangle } from "lucide-react";

interface Task {
  task_id: string;
  title: string;
  status: string;
  priority: number;
  assigned_to: string | null;
  tags: string[];
  created_at: string;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/tasks", {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      const data = await res.json();
      setTasks(data.tasks || []);
    } catch (e) {
      console.error("Failed to load tasks", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTasks(); }, []);

  const statusColor = (status: string) => {
    switch (status) {
      case "completed": return "text-green-400";
      case "running": return "text-blue-400";
      case "failed": return "text-red-400";
      case "pending": return "text-yellow-400";
      default: return "text-text-quaternary";
    }
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-lg font-medium text-foreground">Task Board</h1>
        <p className="mt-1 text-xs text-text-quaternary">
          Tasks dispatched by AgentMesh and HermesLoop across all your agents
        </p>
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center text-sm text-text-quaternary">Loading...</div>
      ) : tasks.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <CheckCircle className="mb-3 h-8 w-8 text-green-400" />
            <p className="text-sm text-text-tertiary">No active tasks</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <Card key={task.task_id}>
              <CardContent className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-medium ${statusColor(task.status)}`}>
                    {task.status}
                  </span>
                  <span className="text-sm text-foreground">{task.title}</span>
                  {task.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-[10px]">{tag}</Badge>
                  ))}
                </div>
                <div className="flex items-center gap-3 text-xs text-text-quaternary">
                  {task.assigned_to && <span>{task.assigned_to}</span>}
                  <span>{new Date(task.created_at).toLocaleDateString()}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
