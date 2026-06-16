import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { IngredientsEditor } from './IngredientsEditor';

describe('IngredientsEditor', () => {
  it('seeds rows from a stored JSON value', () => {
    render(
      <IngredientsEditor
        initialValue='[{"name":"Paracetamol","qty":"500","unit":"mg"}]'
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('Ingredient name 1')).toHaveValue('Paracetamol');
    expect(screen.getByLabelText('Ingredient quantity 1')).toHaveValue('500');
    expect(screen.getByLabelText('Ingredient unit 1')).toHaveValue('mg');
  });

  it('emits serialized JSON as rows are edited and added', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<IngredientsEditor initialValue="" onChange={onChange} />);

    await user.type(screen.getByLabelText('Ingredient name 1'), 'API');
    await user.type(screen.getByLabelText('Ingredient quantity 1'), '10');
    await user.click(screen.getByRole('button', { name: 'Add ingredient' }));
    await user.type(screen.getByLabelText('Ingredient name 2'), 'Filler');

    // Last emission carries both rows serialized to JSON.
    const last = onChange.mock.calls.at(-1)?.[0] as string;
    expect(JSON.parse(last)).toEqual([{ name: 'API', qty: '10' }, { name: 'Filler' }]);
  });

  it('offers raw materials as datalist options and auto-fills the unit on a match', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <IngredientsEditor
        initialValue=""
        onChange={onChange}
        rawMaterials={[
          { name: 'Paracetamol API', unit: 'mg' },
          { name: 'Microcrystalline Cellulose', unit: 'g' },
        ]}
      />,
    );

    // The raw materials are exposed as datalist options for the name combobox
    // (datalist options live in the a11y tree as hidden — hence `hidden: true`).
    expect(screen.getByRole('option', { name: 'Paracetamol API', hidden: true })).toBeInTheDocument();

    // Typing a name that matches a raw material auto-fetches its unit.
    await user.type(screen.getByLabelText('Ingredient name 1'), 'Paracetamol API');
    expect(screen.getByLabelText('Ingredient unit 1')).toHaveValue('mg');

    const last = onChange.mock.calls.at(-1)?.[0] as string;
    expect(JSON.parse(last)).toEqual([{ name: 'Paracetamol API', unit: 'mg' }]);
  });

  it('keeps a free-text ingredient not in the catalog (no forced unit)', async () => {
    const user = userEvent.setup();
    render(
      <IngredientsEditor
        initialValue=""
        onChange={vi.fn()}
        rawMaterials={[{ name: 'Paracetamol API', unit: 'mg' }]}
      />,
    );

    await user.type(screen.getByLabelText('Ingredient name 1'), 'Custom Flavour');
    // No catalog match → unit is left for the operator to fill in manually.
    expect(screen.getByLabelText('Ingredient unit 1')).toHaveValue('');
    await user.type(screen.getByLabelText('Ingredient unit 1'), 'ml');
    expect(screen.getByLabelText('Ingredient unit 1')).toHaveValue('ml');
  });

  it('keeps a legacy free-text value as the first row name', () => {
    render(<IngredientsEditor initialValue="Some free text recipe" onChange={vi.fn()} />);
    expect(screen.getByLabelText('Ingredient name 1')).toHaveValue('Some free text recipe');
  });

  it('removing the only row leaves one blank row and clears the value', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<IngredientsEditor initialValue='[{"name":"API"}]' onChange={onChange} />);

    await user.click(screen.getByRole('button', { name: 'Remove ingredient 1' }));
    expect(screen.getByLabelText('Ingredient name 1')).toHaveValue('');
    expect(onChange).toHaveBeenLastCalledWith('');
  });
});
