import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class Webstore {

    public int buyProduct(int prod, int cc) {
        cc = MultiTainter.taintedInt(cc, "cc_"); // @Phosphor
        int ret;
        ret = prod;
        return ret;
    }

}