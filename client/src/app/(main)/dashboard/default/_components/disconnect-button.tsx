"use client";

import { useState } from "react";
import { Unplug } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

interface DisconnectButtonProps {
  sessionId: string;
  username: string;
  variant?: "compact" | "full";
}

export function DisconnectButton({ sessionId, username, variant = "compact" }: DisconnectButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleDisconnect = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/sessions/active/${sessionId}/disconnect`, {
        method: "POST",
      });

      const data = await response.json();

      if (response.ok && data.success) {
        console.log(`Successfully disconnected ${username}:`, data);
        alert(`Session Disconnected\n\nSuccessfully sent CoA Disconnect for ${username}.\nReply: ${data.reply_code}`);
      } else {
        console.error(`Failed to disconnect ${username}:`, data);
        alert(`Disconnect Failed\n\n${data.error || "Failed to disconnect session"}`);
      }
    } catch (error) {
      console.error("Error disconnecting session:", error);
      alert("Error\n\nAn error occurred while disconnecting the session");
    } finally {
      setIsLoading(false);
      setIsOpen(false);
    }
  };

  return (
    <>
      <Button
        variant={variant == "full" ? "default" : "link"}
        className={cn(
          "cursor-pointer",
          variant === "full" ? "bg-red-500/80 text-white hover:bg-red-300" : "text-red-500 hover:bg-transparent",
          variant === "full" && "px-2",
          variant === "compact" && "h-7 w-7",
        )}
        onClick={() => setIsOpen(true)}
        title="Disconnect session"
      >
        {variant === "full" && "Disconnect"}
        <Unplug className="h-3 w-3" />
      </Button>

      <AlertDialog open={isOpen} onOpenChange={setIsOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Session Disconnect</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to send a CoA Disconnect request for user <strong>{username}</strong>?
              <br />
              <br />
              This will immediately terminate their active session.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDisconnect}
              disabled={isLoading}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isLoading ? "Disconnecting..." : "Disconnect"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
