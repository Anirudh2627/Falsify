import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ClaimInput } from '../components/ClaimInput';

describe('ClaimInput Component', () => {
  it('renders the claim input, character limit counter, and submit button', () => {
    render(
      <ClaimInput
        onVerify={vi.fn()}
        isStreaming={false}
      />
    );

    expect(screen.getByLabelText(/Claim statement to verify/i)).toBeInTheDocument();
    expect(screen.getByText(/0 \/ 4,000 characters/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify Claim/i })).toBeInTheDocument();
  });

  it('validates empty and whitespace-only claims and blocks submission', async () => {
    const onVerifyMock = vi.fn();
    render(
      <ClaimInput
        onVerify={onVerifyMock}
        isStreaming={false}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Verify Claim/i });
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/Claim cannot be empty or whitespace only/i)).toBeInTheDocument();
    expect(onVerifyMock).not.toHaveBeenCalled();

    // Type spaces
    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    await userEvent.type(textarea, '     ');
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/Claim cannot be empty or whitespace only/i)).toBeInTheDocument();
    expect(onVerifyMock).not.toHaveBeenCalled();
  });

  it('enforces the 4,000 character maximum limit', async () => {
    const onVerifyMock = vi.fn();
    render(
      <ClaimInput
        onVerify={onVerifyMock}
        isStreaming={false}
      />
    );

    const textarea = screen.getByLabelText(/Claim statement to verify/i);
    const longText = 'a'.repeat(4001);

    fireEvent.change(textarea, { target: { value: longText } });

    expect(screen.getByText(/4,001 \/ 4,000 characters/i)).toBeInTheDocument();
    const submitBtn = screen.getByRole('button', { name: /Verify Claim/i });
    expect(submitBtn).toBeDisabled();

    fireEvent.click(submitBtn);
    expect(onVerifyMock).not.toHaveBeenCalled();
  });

  it('disables submit button and prevents duplicate submission while streaming', () => {
    const onVerifyMock = vi.fn();
    const onCancelMock = vi.fn();
    render(
      <ClaimInput
        onVerify={onVerifyMock}
        onCancelStream={onCancelMock}
        isStreaming={true}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Verifying Claim/i });
    expect(submitBtn).toBeDisabled();

    // Verify presence of cancel stream button
    const cancelBtn = screen.getByRole('button', { name: /Cancel Stream/i });
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(onCancelMock).toHaveBeenCalledTimes(1);
  });

  it('populates input when clicking a sample preset', async () => {
    render(
      <ClaimInput
        onVerify={vi.fn()}
        isStreaming={false}
      />
    );

    const presetBtn = screen.getByRole('button', { name: /Corporate Revenue Claim/i });
    fireEvent.click(presetBtn);

    const textarea = screen.getByLabelText(/Claim statement to verify/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe('Company X grew revenue by 40% in 2025.');
  });
});
