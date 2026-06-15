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

    public static void main(String[] args) {
        int result = new Webstore().buyProduct(0, 1);
        Taint t = MultiTainter.getTaint(result);
        if (t != null) {
            System.out.println("Phosphor: ret is tainted");
            System.out.println("Phosphor: taint labels " + t);
        }
    }

}